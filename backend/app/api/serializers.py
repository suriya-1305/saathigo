"""Converts ORM entities into viewer-aware response models (hides private fields from strangers)."""
import json

from app.data.countries import country_name
from app.models import ProductRequest, Shipment, ShipmentStatus, User
from app.schemas import OfferOut, ProductRequestOut, PublicUser, ShipmentOut, TripOut
from app.services.storage import public_url


def request_out(req: ProductRequest, viewer: User | None, detail: bool = False) -> ProductRequestOut:
    is_buyer = bool(viewer and viewer.id == req.buyer_id)
    is_traveller = bool(viewer and req.traveller_id and viewer.id == req.traveller_id)
    out = ProductRequestOut(
        id=req.id, product_url=req.product_url, title=req.title, description=req.description,
        image_url=req.image_url, store_name=req.store_name, quantity=req.quantity,
        price_amount=req.price_amount, price_currency=req.price_currency,
        item_price_paise=req.item_price_paise, reward_paise=req.reward_paise,
        service_fee_paise=req.service_fee_paise, total_paise=req.total_paise,
        source_country=req.source_country, source_country_name=country_name(req.source_country),
        deliver_city=req.deliver_city, needed_by=req.needed_by, status=req.status,
        buyer=PublicUser.model_validate(req.buyer),
        traveller=PublicUser.model_validate(req.traveller) if req.traveller else None,
        offers_count=len(req.offers), created_at=req.created_at,
        is_buyer=is_buyer, is_traveller=is_traveller,
    )
    if detail:
        if is_buyer:
            out.offers = [OfferOut.model_validate(o) for o in req.offers]
            out.delivery_otp = req.delivery_otp
        elif viewer:
            out.offers = [OfferOut.model_validate(o) for o in req.offers if o.traveller_id == viewer.id]
        if is_buyer or is_traveller:
            out.purchase_photo_url = public_url(req.purchase_photo)
    return out


def shipment_out(shp: Shipment, viewer: User | None) -> ShipmentOut:
    is_sender = bool(viewer and viewer.id == shp.sender_id)
    is_traveller = bool(viewer and shp.traveller_id and viewer.id == shp.traveller_id)
    out = ShipmentOut(
        id=shp.id, item_name=shp.item_name, description=shp.description, category=shp.category,
        weight_kg=shp.weight_kg, length_cm=shp.length_cm, width_cm=shp.width_cm, height_cm=shp.height_cm,
        declared_value_paise=shp.declared_value_paise, pickup_city=shp.pickup_city,
        destination_country=shp.destination_country,
        destination_country_name=country_name(shp.destination_country),
        destination_city=shp.destination_city, needed_by=shp.needed_by,
        shipping_provider=shp.shipping_provider, courier_estimate_paise=shp.courier_estimate_paise,
        price_paise=shp.price_paise, traveller_payout_paise=shp.traveller_payout_paise, status=shp.status,
        sender=PublicUser.model_validate(shp.sender),
        traveller=PublicUser.model_validate(shp.traveller) if shp.traveller else None,
        trip=TripOut.model_validate(shp.trip) if shp.trip else None,
        handover_photo_url=public_url(shp.handover_photo) if (is_sender or is_traveller) else None,
        handover_at=shp.handover_at,
        delivery_photo_url=public_url(shp.delivery_photo) if (is_sender or is_traveller) else None,
        delivered_at=shp.delivered_at, created_at=shp.created_at,
        compliance_status=shp.compliance_status,
        compliance_report=json.loads(shp.compliance_report) if shp.compliance_report else None,
        is_sender=is_sender, is_traveller=is_traveller,
    )
    paid_states = {ShipmentStatus.PAID, ShipmentStatus.IN_TRANSIT, ShipmentStatus.DELIVERED}
    if is_sender or (is_traveller and shp.status in paid_states):
        out.recipient_name = shp.recipient_name
        out.recipient_phone = shp.recipient_phone
        out.recipient_address = shp.recipient_address
    if is_sender:
        out.delivery_otp = shp.delivery_otp
        out.platform_fee_paise = shp.platform_fee_paise
    return out
