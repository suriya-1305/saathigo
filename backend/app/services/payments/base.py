from dataclasses import dataclass, field
from typing import Mapping, Protocol

from app.models import Payment, User


@dataclass
class CheckoutSession:
    provider_order_id: str
    redirect_url: str
    raw: dict = field(default_factory=dict)


class PaymentProviderError(RuntimeError):
    pass


class PaymentProvider(Protocol):
    name: str

    def create_checkout(self, payment: Payment, user: User, callback_url: str,
                        description: str) -> CheckoutSession: ...

    def fetch_status(self, provider_order_id: str) -> tuple[str, dict]:
        """Return (normalized PaymentStatus value, raw provider payload)."""
        ...

    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool: ...
