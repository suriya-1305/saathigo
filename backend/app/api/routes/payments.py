import html
import json
import logging
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.db import get_db
from app.models import (
    Payment,
    PaymentPurpose,
    PaymentStatus,
    Payout,
    ProductRequest,
    RequestStatus,
    Shipment,
    ShipmentStatus,
    User,
)
from app.schemas import CheckoutIn, CheckoutOut, PaymentOut, PayoutOut
from app.services.escrow import apply_payment_status, successful_payment
from app.services.payments import PaymentProviderError, get_provider
from app.services.payments.mock import MockProvider
from app.services.pricing import buy_pricing

log = logging.getLogger(__name__)
router = APIRouter(tags=["payments"])


def _payable(db: Session, body: CheckoutIn, user: User) -> tuple[int, str]:
    if body.purpose == PaymentPurpose.PRODUCT_REQUEST:
        req = db.get(ProductRequest, body.reference_id)
        if not req or req.buyer_id != user.id:
            raise HTTPException(404, "Request not found")
        if req.status != RequestStatus.ACCEPTED:
            raise HTTPException(409, "Accept a traveller's offer before paying")
        total = buy_pricing(req.item_price_paise, req.quantity, req.reward_paise).total_paise
        return total, f"Order #{req.id}: {req.title}"
    if body.purpose == PaymentPurpose.SHIPMENT:
        shp = db.get(Shipment, body.reference_id)
        if not shp or shp.sender_id != user.id:
            raise HTTPException(404, "Shipment not found")
        if shp.status != ShipmentStatus.MATCHED:
            raise HTTPException(409, "Shipment must be matched with a traveller before paying")
        return shp.price_paise, f"Shipment #{shp.id}: {shp.item_name}"
    raise HTTPException(400, "Unknown payment purpose")


@router.post("/payments/checkout", response_model=CheckoutOut)
def checkout(body: CheckoutIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if successful_payment(db, body.purpose, body.reference_id):
        raise HTTPException(409, "Already paid")
    amount, description = _payable(db, body, user)
    tag = "R" if body.purpose == PaymentPurpose.PRODUCT_REQUEST else "S"
    payment = Payment(
        user_id=user.id, purpose=body.purpose, reference_id=body.reference_id, amount_paise=amount,
        provider=settings.payment_provider,
        merchant_order_reference=f"TA-{tag}{body.reference_id}-{uuid.uuid4().hex[:12]}",
    )
    db.add(payment)
    db.flush()
    callback = f"{settings.backend_url}/api/payments/callback?payment_id={payment.id}"
    try:
        session = get_provider().create_checkout(payment, user, callback, description)
    except PaymentProviderError as exc:
        db.rollback()
        log.error("Checkout creation failed: %s", exc)
        raise HTTPException(502, "Payment gateway unavailable, please try again")
    payment.provider_order_id = session.provider_order_id
    payment.redirect_url = session.redirect_url
    payment.status = PaymentStatus.PENDING
    payment.raw_response = json.dumps(session.raw, default=str)[:20000]
    db.commit()
    return CheckoutOut(payment_id=payment.id, redirect_url=session.redirect_url, provider=payment.provider)


def _refresh(db: Session, payment: Payment) -> Payment:
    if payment.status in (PaymentStatus.SUCCESS, PaymentStatus.REFUNDED) or not payment.provider_order_id:
        return payment
    try:
        status, raw = get_provider().fetch_status(payment.provider_order_id)
    except PaymentProviderError as exc:
        log.warning("Status refresh failed for payment %s: %s", payment.id, exc)
        return payment
    return apply_payment_status(db, payment, status, raw)


@router.api_route("/payments/callback", methods=["GET", "POST"], include_in_schema=False)
def gateway_callback(payment_id: int, db: Session = Depends(get_db)):
    """Pine Labs redirects the payer here. We never trust the redirect params; we re-query the order."""
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "Payment not found")
    _refresh(db, payment)
    return RedirectResponse(f"{settings.frontend_url}/payments/result?payment_id={payment.id}", status_code=303)


@router.post("/payments/pinelabs/webhook", include_in_schema=False)
async def pinelabs_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    provider = get_provider()
    if not provider.verify_webhook(request.headers, body):
        raise HTTPException(401, "Invalid signature")
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")
    data = event.get("data") or event
    order_id = data.get("order_id")
    ref = data.get("merchant_order_reference")
    payment = None
    if order_id:
        payment = db.scalar(select(Payment).where(Payment.provider_order_id == order_id))
    if not payment and ref:
        payment = db.scalar(select(Payment).where(Payment.merchant_order_reference == ref))
    if not payment:
        log.warning("Webhook for unknown order %s / %s", order_id, ref)
        return {"ok": True}
    _refresh(db, payment)
    return {"ok": True}


@router.get("/payments/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    payment = db.get(Payment, payment_id)
    if not payment or payment.user_id != user.id:
        raise HTTPException(404, "Payment not found")
    return _refresh(db, payment)


@router.get("/payouts/mine", response_model=list[PayoutOut])
def my_payouts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Payout).where(Payout.traveller_id == user.id).order_by(Payout.created_at.desc())).all()


# ---------------------------------------------------------------- mock gateway (dev only)

def _mock_payment(db: Session, payment_id: int) -> Payment:
    if settings.payment_provider != "mock":
        raise HTTPException(404, "Not found")
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "Payment not found")
    return payment


@router.get("/payments/mock/checkout/{payment_id}", response_class=HTMLResponse, include_in_schema=False)
def mock_checkout_page(payment_id: int, db: Session = Depends(get_db)):
    p = _mock_payment(db, payment_id)
    amount = f"₹{p.amount_paise / 100:,.2f}"
    action = f"/api/payments/mock/checkout/{p.id}/complete"
    return f"""<!doctype html><html><head><meta name=viewport content="width=device-width,initial-scale=1">
<title>Mock Pine Labs Checkout</title><style>
body{{font-family:system-ui;background:#f4f6fb;display:grid;place-items:center;min-height:100vh;margin:0}}
.card{{background:#fff;padding:32px;border-radius:16px;box-shadow:0 10px 30px #0001;max-width:380px;width:90%}}
button{{width:100%;padding:14px;border:0;border-radius:10px;font-size:16px;margin-top:10px;cursor:pointer}}
.ok{{background:#16a34a;color:#fff}}.bad{{background:#e5e7eb}}</style></head><body><div class=card>
<p style="color:#64748b;margin:0">Mock gateway &middot; set PAYMENT_PROVIDER=pinelabs for real payments</p>
<h2>Pay {html.escape(amount)}</h2><p>Reference: {html.escape(p.merchant_order_reference)}</p>
<form method=post action="{action}"><button class=ok name=result value=success>Pay successfully</button>
<button class=bad name=result value=failed>Simulate failure</button></form></div></body></html>"""


@router.post("/payments/mock/checkout/{payment_id}/complete", include_in_schema=False)
def mock_complete(payment_id: int, result: str = Form(...), db: Session = Depends(get_db)):
    p = _mock_payment(db, payment_id)
    provider = get_provider()
    if isinstance(provider, MockProvider) and p.provider_order_id:
        provider.set_status(p.provider_order_id,
                            PaymentStatus.SUCCESS if result == "success" else PaymentStatus.FAILED)
    return RedirectResponse(f"/api/payments/callback?payment_id={p.id}", status_code=303)
