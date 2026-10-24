import json
from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.serializers import shipment_out
from app.core.deps import get_current_user, get_optional_user
from app.data.countries import country_name
from app.db import get_db
from app.models import PaymentPurpose, Shipment, ShipmentStatus, User
from app.schemas import AcceptShipmentIn, CountryGroup, ShipmentIn, ShipmentOut

from app.services import agents, escrow
from app.services.pricing import send_pricing
from app.services.storage import save_photo
from app.services.trip_link import resolve_trip
from app.services.weight import estimate_weight

router = APIRouter(prefix="/shipments", tags=["send-overseas"])


@router.post("", response_model=ShipmentOut, status_code=201)
def create_shipment(body: ShipmentIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.destination_country == "IN":
        raise HTTPException(400, "Destination must be outside India")
    items = agents.shipment_items(body.item_name, body.description)
    report = agents.read_compliance_token(body.compliance_token, user.id, items, body.destination_country) \
        if body.compliance_token else None
    if report is None:
        outcome = agents.saathi.check_compliance(items, "IN", body.destination_country)
        report = {**outcome.data, "meta": outcome.meta()}
    else:
        outcome = None
    # Only prohibited items stop a listing; "needs label check" items are shown to travellers as a note.
    if report["overall"] == "blocked":
        blocked = [i["item"] for i in report["items"] if i["status"] == "not_allowed"]
        raise HTTPException(422, {"message": "Saathi Compliance: some items are not allowed on this route. "
                                             "Remove them and try again.", "blocked_items": blocked,
                                  "compliance": report})
    p = send_pricing(body.declared_value_inr * 100)
    shp = Shipment(
        sender_id=user.id, item_name=body.item_name, description=body.description,
        category=body.category or agents.saathi._guess_category(f"{body.item_name} {body.description or ''}"),
        weight_kg=body.weight_kg or 0, declared_value_paise=p.value_paise, pickup_city=body.pickup_city,
        destination_country=body.destination_country, destination_city=body.destination_city,
        recipient_name=body.recipient_name or "", recipient_phone=body.recipient_phone or "",
        recipient_address=body.recipient_address or "", needed_by=body.needed_by,
        shipping_provider="value_based", courier_estimate_paise=0,
        price_paise=p.price_paise, traveller_payout_paise=p.traveller_payout_paise,
        platform_fee_paise=p.platform_fee_paise,
        compliance_status=report["overall"], compliance_report=json.dumps(report, default=str),
    )
    db.add(shp)
    db.flush()
    if outcome is not None:
        agents.log_run(db, outcome, user.id, f"Compliance: {report['overall']} ({len(items)} items)",
                       "shipment", shp.id)
    db.commit()
    db.refresh(shp)
    return shipment_out(shp, user)

@router.get("/grouped", response_model=list[CountryGroup])
def grouped_by_destination(viewer: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Shipment).where(Shipment.status == ShipmentStatus.OPEN)
                      .order_by(Shipment.created_at.desc()).limit(1000)).all()
    groups: dict[str, list] = defaultdict(list)
    for s in rows:
        groups[s.destination_country].append(s)
    result = [
        CountryGroup(country=c, country_name=country_name(c), count=len(items),
                     items=[shipment_out(s, viewer) for s in items[:12]])
        for c, items in groups.items()
    ]
    return sorted(result, key=lambda g: -g.count)


@router.get("/mine", response_model=list[ShipmentOut])
def my_shipments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Shipment).where(Shipment.sender_id == user.id).order_by(Shipment.created_at.desc())).all()
    return [shipment_out(s, user) for s in rows]


@router.get("/carrying", response_model=list[ShipmentOut])
def carrying(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Shipment).where(Shipment.traveller_id == user.id)
                      .order_by(Shipment.updated_at.desc())).all()
    return [shipment_out(s, user) for s in rows]


def _get(db: Session, shipment_id: int) -> Shipment:
    shp = db.get(Shipment, shipment_id)
    if not shp:
        raise HTTPException(404, "Shipment not found")
    return shp


@router.get("/{shipment_id}", response_model=ShipmentOut)
def get_shipment(shipment_id: int, viewer: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    return shipment_out(_get(db, shipment_id), viewer)


@router.post("/{shipment_id}/accept", response_model=ShipmentOut)
def accept(shipment_id: int, body: AcceptShipmentIn, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    """Anyone flying India -> destination can take the parcel; a trip is linked or recorded automatically."""
    shp = _get(db, shipment_id)
    if shp.sender_id == user.id:
        raise HTTPException(400, "You cannot carry your own shipment")
    if shp.status != ShipmentStatus.OPEN:
        raise HTTPException(409, "Shipment already taken")
    trip = resolve_trip(db, user, origin_country="IN", origin_city=shp.pickup_city,
                        destination_country=shp.destination_country, destination_city=shp.destination_city,
                        trip_id=body.trip_id, travel_date=body.travel_date, needed_by=shp.needed_by,
                        weight_kg=shp.weight_kg or None)
    shp.traveller_id = user.id
    shp.trip_id = trip.id
    shp.status = ShipmentStatus.MATCHED
    db.commit()
    db.refresh(shp)
    return shipment_out(shp, user)


@router.post("/{shipment_id}/release", response_model=ShipmentOut)
def release(shipment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Sender declines or traveller backs out before payment; shipment goes back to the open pool."""
    shp = _get(db, shipment_id)
    if user.id not in (shp.sender_id, shp.traveller_id):
        raise HTTPException(403, "Not allowed")
    if shp.status != ShipmentStatus.MATCHED:
        raise HTTPException(409, "Only matched, unpaid shipments can be released")
    shp.traveller_id = None
    shp.trip_id = None
    shp.status = ShipmentStatus.OPEN
    db.commit()
    db.refresh(shp)
    return shipment_out(shp, user)


@router.post("/{shipment_id}/cancel", response_model=ShipmentOut)
def cancel(shipment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    shp = _get(db, shipment_id)
    if shp.sender_id != user.id:
        raise HTTPException(403, "Only the sender can cancel")
    if shp.status not in (ShipmentStatus.OPEN, ShipmentStatus.MATCHED):
        raise HTTPException(409, "Paid shipments can only be cancelled via support (refund flow)")
    shp.status = ShipmentStatus.CANCELLED
    db.commit()
    return shipment_out(shp, user)


@router.post("/{shipment_id}/handover", response_model=ShipmentOut)
async def handover(shipment_id: int, photo: UploadFile = File(...), user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """Traveller photographs the item when the sender hands it over (authenticity proof)."""
    shp = _get(db, shipment_id)
    if shp.traveller_id != user.id:
        raise HTTPException(403, "Only the assigned traveller can do this")
    if shp.status != ShipmentStatus.PAID:
        raise HTTPException(409, "Sender has not paid yet")
    shp.handover_photo = await save_photo(photo, f"shp{shp.id}-handover")
    shp.handover_at = datetime.now(UTC)
    shp.status = ShipmentStatus.IN_TRANSIT
    db.commit()
    return shipment_out(shp, user)


@router.post("/{shipment_id}/deliver", response_model=ShipmentOut)
async def deliver(shipment_id: int, otp: str = Form(..., min_length=4, max_length=6),
                  photo: UploadFile | None = File(default=None),
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Traveller enters the recipient's OTP (shared by the sender) to complete and release payout."""
    shp = _get(db, shipment_id)
    if shp.traveller_id != user.id:
        raise HTTPException(403, "Only the assigned traveller can do this")
    if shp.status != ShipmentStatus.IN_TRANSIT:
        raise HTTPException(409, "Capture the handover photo first")
    if not shp.delivery_otp or otp.strip() != shp.delivery_otp:
        raise HTTPException(400, "Incorrect OTP")
    if photo is not None and photo.filename:
        shp.delivery_photo = await save_photo(photo, f"shp{shp.id}-delivery")
    shp.status = ShipmentStatus.DELIVERED
    shp.delivered_at = datetime.now(UTC)
    escrow.release_payout(db, user.id, PaymentPurpose.SHIPMENT, shp.id, shp.traveller_payout_paise)
    db.commit()
    return shipment_out(shp, user)
