"""Countries supported on the platform with currency and courier zone.

Zones drive the built-in rate-card estimator (see services/shipping/rate_card.py).
"""

COUNTRIES: dict[str, dict[str, str]] = {
    "IN": {"name": "India", "currency": "INR", "zone": "DOM"},
    "AE": {"name": "United Arab Emirates", "currency": "AED", "zone": "A"},
    "SA": {"name": "Saudi Arabia", "currency": "SAR", "zone": "A"},
    "QA": {"name": "Qatar", "currency": "QAR", "zone": "A"},
    "KW": {"name": "Kuwait", "currency": "KWD", "zone": "A"},
    "OM": {"name": "Oman", "currency": "OMR", "zone": "A"},
    "BH": {"name": "Bahrain", "currency": "BHD", "zone": "A"},
    "SG": {"name": "Singapore", "currency": "SGD", "zone": "B"},
    "MY": {"name": "Malaysia", "currency": "MYR", "zone": "B"},
    "TH": {"name": "Thailand", "currency": "THB", "zone": "B"},
    "HK": {"name": "Hong Kong", "currency": "HKD", "zone": "B"},
    "JP": {"name": "Japan", "currency": "JPY", "zone": "B"},
    "CN": {"name": "China", "currency": "CNY", "zone": "B"},
    "LK": {"name": "Sri Lanka", "currency": "LKR", "zone": "B"},
    "NP": {"name": "Nepal", "currency": "NPR", "zone": "B"},
    "GB": {"name": "United Kingdom", "currency": "GBP", "zone": "C"},
    "DE": {"name": "Germany", "currency": "EUR", "zone": "C"},
    "FR": {"name": "France", "currency": "EUR", "zone": "C"},
    "NL": {"name": "Netherlands", "currency": "EUR", "zone": "C"},
    "IT": {"name": "Italy", "currency": "EUR", "zone": "C"},
    "ES": {"name": "Spain", "currency": "EUR", "zone": "C"},
    "IE": {"name": "Ireland", "currency": "EUR", "zone": "C"},
    "CH": {"name": "Switzerland", "currency": "CHF", "zone": "C"},
    "US": {"name": "United States", "currency": "USD", "zone": "D"},
    "CA": {"name": "Canada", "currency": "CAD", "zone": "D"},
    "AU": {"name": "Australia", "currency": "AUD", "zone": "E"},
    "NZ": {"name": "New Zealand", "currency": "NZD", "zone": "E"},
}

# Indicative INR conversion rates; replace with a live FX feed in production.
FX_TO_INR: dict[str, float] = {
    "INR": 1.0, "USD": 84.0, "EUR": 91.0, "GBP": 109.0, "AED": 22.9, "SAR": 22.4, "QAR": 23.1,
    "KWD": 273.0, "OMR": 218.0, "BHD": 223.0, "SGD": 64.0, "MYR": 18.5, "THB": 2.4, "HKD": 10.8,
    "JPY": 0.56, "CNY": 11.7, "LKR": 0.28, "NPR": 0.625, "CHF": 95.0, "CAD": 61.0, "AUD": 55.0,
    "NZD": 50.0,
}


def country_name(code: str) -> str:
    return COUNTRIES.get(code.upper(), {}).get("name", code.upper())


def to_inr_paise(amount: float, currency: str) -> int:
    rate = FX_TO_INR.get(currency.upper())
    if rate is None:
        raise ValueError(f"Unsupported currency {currency}")
    return round(amount * rate * 100)
