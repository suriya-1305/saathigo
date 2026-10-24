from functools import lru_cache

from app.core.config import settings
from app.services.payments.base import CheckoutSession, PaymentProvider, PaymentProviderError
from app.services.payments.mock import MockProvider


@lru_cache
def get_provider() -> PaymentProvider:
    if settings.payment_provider == "pinelabs":
        from app.services.payments.pinelabs import PineLabsProvider

        return PineLabsProvider()
    return MockProvider()


__all__ = ["CheckoutSession", "PaymentProvider", "PaymentProviderError", "get_provider"]
