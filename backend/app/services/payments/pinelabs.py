"""Pine Labs Online (Plural) hosted checkout integration.

Flow:
  1. POST /api/auth/v1/token              -> bearer access token (client credentials, cached)
  2. POST /api/checkout/v1/orders         -> { order_id, redirect_url }  (redirect the payer here)
  3. Pine Labs redirects to callback_url  -> we re-fetch the order (source of truth)
  4. GET  /api/pay/v1/orders/{order_id}   -> data.status == PROCESSED means paid
  5. Webhooks (ORDER_PROCESSED, PAYMENT_FAILED, ...) signed with HMAC-SHA256 (webhook-id/timestamp/signature)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import threading
import time
import uuid
from datetime import UTC, datetime
from typing import Mapping

import httpx

from app.core.config import settings
from app.models import Payment, PaymentStatus, User
from app.services.payments.base import CheckoutSession, PaymentProviderError

STATUS_MAP = {
    "PROCESSED": PaymentStatus.SUCCESS,
    "CAPTURED": PaymentStatus.SUCCESS,
    "AUTHORIZED": PaymentStatus.PENDING,
    "CREATED": PaymentStatus.CREATED,
    "PENDING": PaymentStatus.PENDING,
    "ATTEMPTED": PaymentStatus.PENDING,
    "FAILED": PaymentStatus.FAILED,
    "CANCELLED": PaymentStatus.CANCELLED,
    "FULLY_REFUNDED": PaymentStatus.REFUNDED,
    "REFUNDED": PaymentStatus.REFUNDED,
}
WEBHOOK_TOLERANCE_SECONDS = 5 * 60


class PineLabsProvider:
    name = "pinelabs"

    def __init__(self) -> None:
        if not (settings.pinelabs_client_id and settings.pinelabs_client_secret):
            raise PaymentProviderError("PINELABS_CLIENT_ID / PINELABS_CLIENT_SECRET are not configured")
        self.base = settings.pinelabs_api_base
        self._token: str | None = None
        self._token_expiry = 0.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ auth
    def _access_token(self) -> str:
        with self._lock:
            if self._token and time.time() < self._token_expiry - 60:
                return self._token
            resp = httpx.post(
                f"{self.base}/api/auth/v1/token",
                json={
                    "client_id": settings.pinelabs_client_id,
                    "client_secret": settings.pinelabs_client_secret,
                    "grant_type": "client_credentials",
                },
                timeout=15,
            )
            if resp.status_code >= 400:
                raise PaymentProviderError(f"Pine Labs auth failed: {resp.status_code} {resp.text[:300]}")
            data = resp.json()
            self._token = data["access_token"]
            expires_at = data.get("expires_at")
            try:
                self._token_expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00")).timestamp()
            except (AttributeError, ValueError):
                self._token_expiry = time.time() + 30 * 60
            return self._token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Request-ID": str(uuid.uuid4()),
            "Request-Timestamp": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        }

    # ------------------------------------------------------------------ checkout
    def create_checkout(self, payment: Payment, user: User, callback_url: str,
                        description: str) -> CheckoutSession:
        first, _, last = user.name.partition(" ")
        customer: dict = {"email_id": user.email, "first_name": first[:50], "last_name": (last or first)[:50]}
        if user.phone:
            customer.update({"mobile_number": user.phone[-10:], "country_code": "91"})
        body = {
            "merchant_order_reference": payment.merchant_order_reference,
            "order_amount": {"value": payment.amount_paise, "currency": payment.currency},
            "integration_mode": "REDIRECT",
            "pre_auth": False,
            "allowed_payment_methods": ["CARD", "UPI", "NETBANKING", "WALLET", "POINTS"],
            "notes": description[:200],
            "callback_url": callback_url,
            "failure_callback_url": callback_url,
            "purchase_details": {"customer": customer},
        }
        resp = httpx.post(f"{self.base}/api/checkout/v1/orders", json=body, headers=self._headers(), timeout=20)
        if resp.status_code >= 400:
            raise PaymentProviderError(f"Pine Labs checkout failed: {resp.status_code} {resp.text[:500]}")
        data = resp.json()
        if not data.get("redirect_url") or not data.get("order_id"):
            raise PaymentProviderError(f"Unexpected Pine Labs response: {data}")
        return CheckoutSession(provider_order_id=data["order_id"], redirect_url=data["redirect_url"], raw=data)

    def fetch_status(self, provider_order_id: str) -> tuple[str, dict]:
        resp = httpx.get(f"{self.base}/api/pay/v1/orders/{provider_order_id}", headers=self._headers(), timeout=15)
        if resp.status_code >= 400:
            raise PaymentProviderError(f"Pine Labs order lookup failed: {resp.status_code} {resp.text[:300]}")
        payload = resp.json()
        status = str((payload.get("data") or payload).get("status", "")).upper()
        return STATUS_MAP.get(status, PaymentStatus.PENDING), payload

    def refund(self, provider_order_id: str, amount_paise: int, reference: str) -> dict:
        resp = httpx.post(
            f"{self.base}/api/pay/v1/refunds/{provider_order_id}",
            json={"merchant_order_reference": reference,
                  "order_amount": {"value": amount_paise, "currency": "INR"}},
            headers=self._headers(), timeout=20,
        )
        if resp.status_code >= 400:
            raise PaymentProviderError(f"Pine Labs refund failed: {resp.status_code} {resp.text[:300]}")
        return resp.json()

    # ------------------------------------------------------------------ webhooks
    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool:
        secret = settings.pinelabs_webhook_secret
        webhook_id = headers.get("webhook-id")
        timestamp = headers.get("webhook-timestamp")
        signatures = headers.get("webhook-signature")
        if not (secret and webhook_id and timestamp and signatures):
            return False
        try:
            if abs(time.time() - int(timestamp)) > WEBHOOK_TOLERANCE_SECONDS:
                return False
            key = base64.b64decode(secret.removeprefix("whsec_"))
        except ValueError:
            return False
        signed = f"{webhook_id}.{timestamp}.".encode() + body
        expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
        for part in signatures.split():
            _, _, sig = part.partition(",")
            if hmac.compare_digest(sig, expected):
                return True
        return False
