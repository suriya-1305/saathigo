import logging

from app.core.config import settings
from app.services.shipping.base import ShippingQuote
from app.services.shipping.rate_card import RateCardEstimator
from app.services.shipping.shiprocket import ShiprocketEstimator

log = logging.getLogger(__name__)
_fallback = RateCardEstimator()


def estimate_shipping(**kwargs) -> ShippingQuote:
    provider = settings.shipping_provider
    if provider == "shiprocket":
        try:
            return ShiprocketEstimator().estimate(**kwargs)
        except NotImplementedError:
            pass
        except Exception:
            log.exception("Shiprocket estimate failed, using rate card")
    return _fallback.estimate(**kwargs)


__all__ = ["ShippingQuote", "estimate_shipping"]
