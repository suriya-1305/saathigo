"""Built-in international express courier rate card (indicative INR rates from India).

Mirrors how courier aggregators price: chargeable weight = max(actual, volumetric),
billed in 0.5 kg slabs, plus fuel surcharge and 18% GST.
"""

import math

from app.data.countries import COUNTRIES
from app.services.shipping.base import ShippingQuote

# zone -> (first 0.5 kg, each additional 0.5 kg) in rupees
ZONE_RATES: dict[str, tuple[int, int]] = {
    "A": (1450, 420),   # GCC
    "B": (1650, 480),   # South/East Asia
    "C": (2350, 640),   # Europe / UK
    "D": (2650, 720),   # USA / Canada
    "E": (2550, 700),   # Australia / NZ
}
FUEL_SURCHARGE = 0.22
GST = 0.18
VOLUMETRIC_DIVISOR = 5000


class RateCardEstimator:
    name = "rate_card"

    def estimate(self, *, origin_city: str, destination_country: str, weight_kg: float,
                 length_cm: float, width_cm: float, height_cm: float,
                 declared_value_paise: int) -> ShippingQuote:
        country = COUNTRIES.get(destination_country.upper())
        if not country or country["zone"] not in ZONE_RATES:
            raise ValueError(f"Shipping to {destination_country} is not supported")
        zone = country["zone"]
        volumetric = (length_cm * width_cm * height_cm) / VOLUMETRIC_DIVISOR if length_cm and width_cm and height_cm else 0
        chargeable = max(weight_kg, volumetric, 0.5)
        slabs = math.ceil(chargeable / 0.5)
        first, additional = ZONE_RATES[zone]
        base = first + additional * (slabs - 1)
        fuel = base * FUEL_SURCHARGE
        gst = (base + fuel) * GST
        total_rupees = base + fuel + gst
        return ShippingQuote(
            provider=self.name,
            courier_cost_paise=round(total_rupees * 100),
            chargeable_weight_kg=round(slabs * 0.5, 2),
            zone=zone,
            breakdown={
                "base_paise": round(base * 100),
                "fuel_surcharge_paise": round(fuel * 100),
                "gst_paise": round(gst * 100),
                "volumetric_weight_kg": round(volumetric, 2),
            },
        )
