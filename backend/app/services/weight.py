"""Estimate parcel weight when the sender doesn't give one.

Each category / item type has a typical packed size (L x W x H cm) and actual weight. The chargeable
weight is the airline/courier convention: max(actual, volumetric) where volumetric = L*W*H / 5000.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

VOLUMETRIC_DIVISOR = 5000

# (pattern, actual_kg, (L, W, H)) - checked before the category default; first match wins.
_ITEM_PROFILES: list[tuple[str, float, tuple[float, float, float]]] = [
    (r"laptop|macbook", 2.2, (40, 30, 8)),
    (r"saree|sari|lehenga", 0.8, (35, 28, 6)),
    (r"kurta|shirt|dress|top|ethnic wear|dupatta|shawl", 0.4, (30, 25, 5)),
    (r"jacket|sweater|hoodie|blanket", 1.0, (40, 30, 10)),
    (r"shoe|sneaker|nike|adidas", 1.0, (34, 22, 13)),
    (r"phone|iphone|earbud|airpod|charger|watch|tracker", 0.3, (18, 12, 6)),
    (r"camera|kindle|tablet|ipad", 0.7, (25, 20, 8)),
    (r"laddoo|ladoo|mithai|sweet|katli|barfi", 1.0, (25, 20, 8)),
    (r"pickle|achar|jar", 0.8, (20, 15, 12)),
    (r"masala|spice|tea|coffee|namkeen|snack", 0.6, (25, 18, 8)),
    (r"rakhi|greeting card|card|letter", 0.15, (25, 18, 2)),
    (r"document|certificate|paper|passport", 0.3, (33, 25, 2)),
    (r"book|novel", 0.8, (25, 18, 5)),
    (r"medicine|tablet|syrup", 0.3, (15, 10, 8)),
    (r"perfume|cosmetic|cream|sunscreen", 0.4, (18, 12, 8)),
    (r"toy|lego", 0.8, (30, 25, 12)),
    (r"diya|decor|idol|frame", 0.8, (25, 20, 12)),
]

_CATEGORY_DEFAULTS: dict[str, tuple[float, tuple[float, float, float]]] = {
    "documents": (0.3, (33, 25, 2)),
    "clothing": (0.6, (30, 25, 8)),
    "food_sealed": (1.0, (25, 20, 10)),
    "gifts": (0.8, (25, 20, 10)),
    "books": (0.8, (25, 18, 5)),
    "electronics_small": (0.5, (20, 15, 8)),
    "medicines_prescribed": (0.3, (15, 10, 8)),
    "other": (1.0, (30, 20, 15)),
}

_NUM_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "pair": 1}


@dataclass(frozen=True)
class WeightEstimate:
    actual_kg: float
    volumetric_kg: float
    chargeable_kg: float
    length_cm: float
    width_cm: float
    height_cm: float


def _stated_kg(text: str) -> float | None:
    total = sum(float(m) for m in re.findall(r"(\d+(?:\.\d+)?)\s*(?:kg|kgs|kilo)", text))
    grams = sum(float(m) for m in re.findall(r"(\d+(?:\.\d+)?)\s*(?:g|gm|gms|grams)\b", text))
    total += grams / 1000
    return total or None


def _quantity(text: str) -> int:
    m = re.search(r"\b(\d{1,2}|a|an|one|two|three|four|five|six)\s*(?:x\s*)?(?:sets?|pieces?|pcs|boxes|box|packs?|"
                  r"pairs?|kurtas?|sarees?|shirts?|books?|jars?|items?)\b", text)
    if not m:
        m = re.search(r"\((\d{1,2})\s*\w*\)", text)
    if not m:  # "3 novels", "2x mugs" - any count noun that isn't a unit
        m = re.search(r"\b(\d{1,2})\s*(?:x\s*)?(?!(?:kgs?|gms?|grams?|ml|ltrs?|litres?|cm|mm|inch(?:es)?|years?|yrs?|"
                      r"months?|days?)\b)[a-z]{3,}", text)
    if not m:
        return 1
    raw = m.group(1)
    return max(1, min(10, int(raw) if raw.isdigit() else _NUM_WORDS.get(raw, 1)))


def estimate_weight(category: str | None, item_name: str, description: str | None = None) -> WeightEstimate:
    text = f"{item_name} {description or ''}".lower()
    actual, dims = _CATEGORY_DEFAULTS.get(category or "other", _CATEGORY_DEFAULTS["other"])
    for pattern, kg, size in _ITEM_PROFILES:
        if re.search(rf"\b(?:{pattern})", text):
            actual, dims = kg, size
            break
    qty = _quantity(text)
    length, width, height = dims
    if qty > 1:
        actual *= qty
        height = min(60.0, height * qty)
    stated = _stated_kg(text)
    if stated:
        # Explicit weight wins, but mixed parcels ("1 kg laddoos + 2 kurtas") keep the larger estimate.
        actual = max(stated, actual) if qty > 1 else stated
    actual = round(min(actual, 23.0), 2)
    volumetric = round(length * width * height / VOLUMETRIC_DIVISOR, 2)
    chargeable = round(min(max(actual, volumetric, 0.1), 23.0), 1)
    return WeightEstimate(actual, volumetric, chargeable, length, width, height)
