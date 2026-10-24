from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ShippingQuote:
    provider: str
    courier_cost_paise: int
    chargeable_weight_kg: float
    zone: str
    breakdown: dict = field(default_factory=dict)


class ShippingEstimator(Protocol):
    name: str

    def estimate(self, *, origin_city: str, destination_country: str, weight_kg: float,
                 length_cm: float, width_cm: float, height_cm: float,
                 declared_value_paise: int) -> ShippingQuote: ...
