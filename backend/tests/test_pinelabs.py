import base64
import hashlib
import hmac
import time

from app.core.config import settings
from app.services.payments.pinelabs import PineLabsProvider


def _provider(monkeypatch, secret: str) -> PineLabsProvider:
    monkeypatch.setattr(settings, "pinelabs_client_id", "cid")
    monkeypatch.setattr(settings, "pinelabs_client_secret", "csecret")
    monkeypatch.setattr(settings, "pinelabs_webhook_secret", secret)
    return PineLabsProvider()


def _sign(key: bytes, wid: str, ts: str, body: bytes) -> str:
    return base64.b64encode(hmac.new(key, f"{wid}.{ts}.".encode() + body, hashlib.sha256).digest()).decode()


def test_webhook_signature(monkeypatch):
    key = b"super-secret-webhook-key-123456"
    provider = _provider(monkeypatch, "whsec_" + base64.b64encode(key).decode())
    body = b'{"event_type":"ORDER_PROCESSED","data":{"order_id":"v1-1"}}'
    ts = str(int(time.time()))
    headers = {"webhook-id": "msg_1", "webhook-timestamp": ts,
               "webhook-signature": f"v1,{_sign(key, 'msg_1', ts, body)}"}
    assert provider.verify_webhook(headers, body)
    assert not provider.verify_webhook(headers, body + b" ")
    stale = {**headers, "webhook-timestamp": str(int(time.time()) - 3600)}
    assert not provider.verify_webhook(stale, body)
