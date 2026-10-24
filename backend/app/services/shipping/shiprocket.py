"""Skeleton for a live courier-aggregator integration (e.g. Shiprocket international rates).

Implement `estimate` using the provider's rate API and set SHIPPING_PROVIDER=shiprocket.
On any provider error we fall back to the built-in rate card (see get_estimator()).
"""

from app.services.shipping.base import ShippingQuote


class ShiprocketEstimator:
    name = "shiprocket"

    def __init__(self, email: str = "", password: str = "") -> None:
        self.email = email
        self.password = password

    def estimate(self, *, origin_city: str, destination_country: str, weight_kg: float,
                 length_cm: float, width_cm: float, height_cm: float,
                 declared_value_paise: int) -> ShippingQuote:
        raise NotImplementedError("Wire up the Shiprocket international rate API here")
