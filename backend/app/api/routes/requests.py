from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.serializers import request_out
from app.core.deps import get_current_user, get_optional_user
from app.data.countries import country_name, to_inr_paise
from app.db import get_db
from app.models import (
    Offer,
    OfferStatus,
    PaymentPurpose,
    ProductRequest,
    RequestStatus,
    User,
)
from app.schemas import CountryGroup, LinkPreviewOut, OfferIn, OfferOut, ProductRequestIn, ProductRequestOut
from app.services import escrow, link_preview
from app.services.pricing import buy_pricing
from app.services.storage import save_photo
from app.services.trip_link import resolve_trip

router = APIRouter(prefix="/requests", tags=["buy-from-overseas"])


@router.get("/preview", response_model=LinkPreviewOut)
async def preview(url: str = Query(min_length=8, max_length=2048), user: User = Depends(get_current_user)):
    try:
        return await run_in_threadpool(link_preview.fetch_preview, url)
    except link_preview.LinkPreviewError as exc:
        raise HTTPException(400, str(exc))


@router.post("", response_model=ProductRequestOut, status_code=201)
def create_request(body: ProductRequestIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.source_country == "IN":
        raise HTTPException(400, "Source country must be outside India")
    unit = to_inr_paise(body.price_amount, body.price_currency)
    pricing = buy_pricing(unit, body.quantity)
    req = ProductRequest(
        buyer_id=user.id, product_url=str(body.product_url), title=body.title, description=body.description,
        image_url=str(body.image_url) if body.image_url else None, store_name=body.store_name,
        quantity=body.quantity, price_amount=body.price_amount, price_currency=body.price_currency,
        item_price_paise=unit, reward_paise=pricing.reward_paise, service_fee_paise=pricing.service_fee_paise,
        total_paise=pricing.total_paise, source_country=body.source_country, deliver_city=body.deliver_city,
        needed_by=body.needed_by,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return request_out(req, user, detail=True)


@router.get("", response_model=list[ProductRequestOut])
def list_open(country: str | None = None, viewer: User | None = Depends(get_optional_user),
              db: Session = Depends(get_db)):
    q = select(ProductRequest).where(ProductRequest.status == RequestStatus.OPEN)
    if country:
        q = q.where(ProductRequest.source_country == country.upper())
    rows = db.scalars(q.order_by(ProductRequest.created_at.desc()).limit(200)).all()
    return [request_out(r, viewer) for r in rows]


@router.get("/grouped", response_model=list[CountryGroup])
def grouped_by_country(viewer: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    """Open requests grouped by the country the product must be bought in."""
    rows = db.scalars(select(ProductRequest).where(ProductRequest.status == RequestStatus.OPEN)
                      .order_by(ProductRequest.created_at.desc()).limit(1000)).all()
    groups: dict[str, list] = defaultdict(list)
    for r in rows:
        groups[r.source_country].append(r)
    result = [
        CountryGroup(country=c, country_name=country_name(c), count=len(items),
                     items=[request_out(r, viewer) for r in items[:12]])
        for c, items in groups.items()
    ]
    return sorted(result, key=lambda g: -g.count)


@router.get("/mine", response_model=list[ProductRequestOut])
def my_requests(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(ProductRequest).where(ProductRequest.buyer_id == user.id)
                      .order_by(ProductRequest.created_at.desc())).all()
    return [request_out(r, user) for r in rows]


@router.get("/deliveries", response_model=list[ProductRequestOut])
def my_deliveries(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(ProductRequest).where(ProductRequest.traveller_id == user.id)
                      .order_by(ProductRequest.updated_at.desc())).all()
    return [request_out(r, user) for r in rows]


@router.get("/offers/mine", response_model=list[OfferOut])
def my_offers(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Offer).where(Offer.traveller_id == user.id).order_by(Offer.created_at.desc())).all()


def _get(db: Session, request_id: int) -> ProductRequest:
    req = db.get(ProductRequest, request_id)
    if not req:
        raise HTTPException(404, "Request not found")
    return req


@router.get("/{request_id}", response_model=ProductRequestOut)
def get_request(request_id: int, viewer: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    return request_out(_get(db, request_id), viewer, detail=True)


@router.post("/{request_id}/offers", response_model=OfferOut, status_code=201)
def make_offer(request_id: int, body: OfferIn, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    req = _get(db, request_id)
    if req.buyer_id == user.id:
        raise HTTPException(400, "You cannot offer on your own request")
    if req.status != RequestStatus.OPEN:
        raise HTTPException(409, "Request is no longer accepting offers")
    trip = resolve_trip(db, user, origin_country=req.source_country, origin_city=country_name(req.source_country),
                        destination_country="IN", destination_city=req.deliver_city, trip_id=body.trip_id,
                        travel_date=body.travel_date, needed_by=req.needed_by)
    existing = db.scalar(select(Offer).where(Offer.request_id == req.id, Offer.traveller_id == user.id,
                                             Offer.status == OfferStatus.PENDING))
    if existing:
        raise HTTPException(409, "You already have a pending offer on this request")
    offer = Offer(request_id=req.id, traveller_id=user.id, trip_id=trip.id,
                  reward_paise=req.reward_paise,
                  expected_delivery=body.expected_delivery, message=body.message)
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer


@router.post("/{request_id}/offers/{offer_id}/withdraw", response_model=OfferOut)
def withdraw_offer(request_id: int, offer_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    offer = db.get(Offer, offer_id)
    if not offer or offer.request_id != request_id or offer.traveller_id != user.id:
        raise HTTPException(404, "Offer not found")
    if offer.status != OfferStatus.PENDING:
        raise HTTPException(409, "Only pending offers can be withdrawn")
    offer.status = OfferStatus.WITHDRAWN
    db.commit()
    return offer


@router.post("/{request_id}/offers/{offer_id}/accept", response_model=ProductRequestOut)
def accept_offer(request_id: int, offer_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    req = _get(db, request_id)
    if req.buyer_id != user.id:
        raise HTTPException(403, "Only the buyer can accept offers")
    if req.status != RequestStatus.OPEN:
        raise HTTPException(409, "Request is not open")
    offer = db.get(Offer, offer_id)
    if not offer or offer.request_id != req.id or offer.status != OfferStatus.PENDING:
        raise HTTPException(404, "Offer not found")

    for o in req.offers:
        if o.id != offer.id and o.status == OfferStatus.PENDING:
            o.status = OfferStatus.REJECTED
    offer.status = OfferStatus.ACCEPTED
    pricing = buy_pricing(req.item_price_paise, req.quantity)
    req.reward_paise = pricing.reward_paise
    req.service_fee_paise = pricing.service_fee_paise
    req.total_paise = pricing.total_paise
    req.traveller_id = offer.traveller_id
    req.accepted_offer_id = offer.id
    req.status = RequestStatus.ACCEPTED
    db.commit()
    db.refresh(req)
    return request_out(req, user, detail=True)


@router.post("/{request_id}/cancel", response_model=ProductRequestOut)
def cancel_request(request_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = _get(db, request_id)
    if req.buyer_id != user.id:
        raise HTTPException(403, "Only the buyer can cancel")
    if req.status not in (RequestStatus.OPEN, RequestStatus.ACCEPTED):
        raise HTTPException(409, "Paid orders can only be cancelled via support (refund flow)")
    req.status = RequestStatus.CANCELLED
    for o in req.offers:
        if o.status in (OfferStatus.PENDING, OfferStatus.ACCEPTED):
            o.status = OfferStatus.REJECTED
    db.commit()
    return request_out(req, user, detail=True)


@router.post("/{request_id}/purchased", response_model=ProductRequestOut)
async def mark_purchased(request_id: int, photo: UploadFile = File(...), user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    req = _get(db, request_id)
    if req.traveller_id != user.id:
        raise HTTPException(403, "Only the assigned traveller can do this")
    if req.status != RequestStatus.PAID:
        raise HTTPException(409, "Wait for the buyer's payment before purchasing")
    req.purchase_photo = await save_photo(photo, f"req{req.id}-purchase")
    req.purchased_at = datetime.now(UTC)
    req.status = RequestStatus.PURCHASED
    db.commit()
    return request_out(req, user, detail=True)


@router.post("/{request_id}/deliver", response_model=ProductRequestOut)
def deliver(request_id: int, otp: str = Form(..., min_length=4, max_length=6),
            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Traveller enters the OTP the buyer shares at hand-off; releases escrow to the traveller."""
    req = _get(db, request_id)
    if req.traveller_id != user.id:
        raise HTTPException(403, "Only the assigned traveller can do this")
    if req.status != RequestStatus.PURCHASED:
        raise HTTPException(409, "Mark the item as purchased first")
    if not req.delivery_otp or otp.strip() != req.delivery_otp:
        raise HTTPException(400, "Incorrect OTP")
    req.status = RequestStatus.DELIVERED
    req.delivered_at = datetime.now(UTC)
    escrow.release_payout(db, user.id, PaymentPurpose.PRODUCT_REQUEST, req.id,
                          req.item_price_paise * req.quantity + req.reward_paise)
    db.commit()
    return request_out(req, user, detail=True)
