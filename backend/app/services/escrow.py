"""Escrow bookkeeping: reacts to payment outcomes and releases traveller payouts."""

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import generate_otp
from app.models import (
    Payment,
    PaymentPurpose,
    PaymentStatus,
    Payout,
    ProductRequest,
    RequestStatus,
    Shipment,
    ShipmentStatus,
)

log = logging.getLogger(__name__)


def apply_payment_status(db: Session, payment: Payment, status: str, raw: dict | None = None) -> Payment:
    """Idempotently move a payment to `status` and update the paid-for entity."""
    if raw is not None:
        payment.raw_response = json.dumps(raw, default=str)[:20000]
    if payment.status == PaymentStatus.SUCCESS or payment.status == status:
        db.commit()
        return payment

    payment.status = status
    if status == PaymentStatus.SUCCESS:
        _mark_entity_paid(db, payment)
    db.commit()
    return payment


def _mark_entity_paid(db: Session, payment: Payment) -> None:
    if payment.purpose == PaymentPurpose.PRODUCT_REQUEST:
        req = db.get(ProductRequest, payment.reference_id)
        if req and req.status == RequestStatus.ACCEPTED:
            req.status = RequestStatus.PAID
            req.delivery_otp = generate_otp()
        elif req:
            log.warning("Payment %s succeeded for request %s in status %s", payment.id, req.id, req.status)
    elif payment.purpose == PaymentPurpose.SHIPMENT:
        shp = db.get(Shipment, payment.reference_id)
        if shp and shp.status == ShipmentStatus.MATCHED:
            shp.status = ShipmentStatus.PAID
            shp.delivery_otp = generate_otp()
        elif shp:
            log.warning("Payment %s succeeded for shipment %s in status %s", payment.id, shp.id, shp.status)


def successful_payment(db: Session, purpose: str, reference_id: int) -> Payment | None:
    return db.scalar(
        select(Payment).where(
            Payment.purpose == purpose,
            Payment.reference_id == reference_id,
            Payment.status == PaymentStatus.SUCCESS,
        )
    )


def release_payout(db: Session, traveller_id: int, purpose: str, reference_id: int, amount_paise: int) -> Payout:
    """Record the traveller payout. Settlement to bank/UPI happens via Pine Labs Payouts (ops/admin job)."""
    existing = db.scalar(select(Payout).where(Payout.purpose == purpose, Payout.reference_id == reference_id))
    if existing:
        return existing
    payout = Payout(traveller_id=traveller_id, purpose=purpose, reference_id=reference_id,
                    amount_paise=amount_paise)
    db.add(payout)
    return payout
