"""Local stand-in for Pine Labs so the full flow can be demoed without credentials."""

from typing import Mapping

from app.core.config import settings
from app.models import Payment, PaymentStatus, User
from app.services.payments.base import CheckoutSession

# Mock "gateway" state, keyed by provider order id.
_MOCK_ORDERS: dict[str, str] = {}


class MockProvider:
    name = "mock"

    def create_checkout(self, payment: Payment, user: User, callback_url: str,
                        description: str) -> CheckoutSession:
        order_id = f"mock-{payment.merchant_order_reference}"
        _MOCK_ORDERS[order_id] = PaymentStatus.CREATED
        return CheckoutSession(
            provider_order_id=order_id,
            redirect_url=f"{settings.backend_url}/api/payments/mock/checkout/{payment.id}",
            raw={"order_id": order_id, "mock": True},
        )

    def fetch_status(self, provider_order_id: str) -> tuple[str, dict]:
        status = _MOCK_ORDERS.get(provider_order_id, PaymentStatus.PENDING)
        return status, {"order_id": provider_order_id, "status": status}

    def set_status(self, provider_order_id: str, status: str) -> None:
        _MOCK_ORDERS[provider_order_id] = status

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool:
        return False
