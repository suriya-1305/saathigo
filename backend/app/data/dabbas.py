"""Ready-made boxes ("dabbas") the Saathi Dabba Curator turns into normal orders.

Swadeshi dabbas travel India -> abroad (send module); Videshi dabbas travel abroad -> India (buy module).
The curator may only pick from ``candidates`` so it never invents products we cannot price or vet.
"""

DABBAS: list[dict] = [
    {
        "id": "swadeshi-diwali", "kind": "swadeshi", "emoji": "🪔", "name": "Swadeshi Diwali Dabba",
        "tagline": "Mithai, namkeen and diyas for family abroad", "category": "food_sealed", "max_weight_kg": 3.0,
        "candidates": [
            {"name": "Kaju katli (sealed box)", "unit": "box", "approx_weight_kg": 0.5, "approx_value_inr": 650},
            {"name": "Soan papdi (sealed box)", "unit": "box", "approx_weight_kg": 0.5, "approx_value_inr": 250},
            {"name": "Bhujia / namkeen (sealed pack)", "unit": "pack", "approx_weight_kg": 0.4, "approx_value_inr": 180},
            {"name": "Dry fruits gift tin", "unit": "tin", "approx_weight_kg": 0.5, "approx_value_inr": 900},
            {"name": "Clay diyas (set of 6)", "unit": "set", "approx_weight_kg": 0.4, "approx_value_inr": 200},
            {"name": "Rangoli colours kit", "unit": "kit", "approx_weight_kg": 0.3, "approx_value_inr": 150},
            {"name": "Greeting card", "unit": "piece", "approx_weight_kg": 0.05, "approx_value_inr": 50},
        ],
    },
    {
        "id": "swadeshi-ghar-ka-swaad", "kind": "swadeshi", "emoji": "🍛", "name": "Ghar ka Swaad Dabba",
        "tagline": "Masalas, pickles and staples from home", "category": "food_sealed", "max_weight_kg": 4.0,
        "candidates": [
            {"name": "Garam masala (sealed retail pack)", "unit": "pack", "approx_weight_kg": 0.2, "approx_value_inr": 120},
            {"name": "Sambar powder (sealed retail pack)", "unit": "pack", "approx_weight_kg": 0.2, "approx_value_inr": 110},
            {"name": "Mango pickle (sealed jar, labelled)", "unit": "jar", "approx_weight_kg": 0.5, "approx_value_inr": 250},
            {"name": "Instant poha / upma mix", "unit": "pack", "approx_weight_kg": 0.3, "approx_value_inr": 90},
            {"name": "Assam tea (sealed pack)", "unit": "pack", "approx_weight_kg": 0.5, "approx_value_inr": 350},
            {"name": "Papad (sealed pack)", "unit": "pack", "approx_weight_kg": 0.2, "approx_value_inr": 80},
        ],
    },
    {
        "id": "swadeshi-festive-wear", "kind": "swadeshi", "emoji": "👗", "name": "Festive Wear Dabba",
        "tagline": "Kurtas, sarees and accessories for the season", "category": "clothing", "max_weight_kg": 3.0,
        "candidates": [
            {"name": "Cotton kurta", "unit": "piece", "approx_weight_kg": 0.3, "approx_value_inr": 1200},
            {"name": "Silk saree", "unit": "piece", "approx_weight_kg": 0.6, "approx_value_inr": 4500},
            {"name": "Dupatta", "unit": "piece", "approx_weight_kg": 0.2, "approx_value_inr": 600},
            {"name": "Kids' ethnic set", "unit": "set", "approx_weight_kg": 0.4, "approx_value_inr": 1500},
            {"name": "Bangles set (non-precious)", "unit": "set", "approx_weight_kg": 0.2, "approx_value_inr": 300},
        ],
    },
    {
        "id": "swadeshi-rakhi", "kind": "swadeshi", "emoji": "🧵", "name": "Rakhi Dabba",
        "tagline": "Rakhis, roli-chawal and sweets for your brother", "category": "gifts", "max_weight_kg": 1.5,
        "candidates": [
            {"name": "Handmade rakhi", "unit": "piece", "approx_weight_kg": 0.02, "approx_value_inr": 150},
            {"name": "Roli-chawal pack", "unit": "pack", "approx_weight_kg": 0.05, "approx_value_inr": 40},
            {"name": "Chocolates (sealed box)", "unit": "box", "approx_weight_kg": 0.3, "approx_value_inr": 450},
            {"name": "Kaju katli (sealed box)", "unit": "box", "approx_weight_kg": 0.5, "approx_value_inr": 650},
            {"name": "Handwritten card", "unit": "piece", "approx_weight_kg": 0.05, "approx_value_inr": 50},
        ],
    },
    {
        "id": "videshi-chocolates", "kind": "videshi", "emoji": "🍫", "name": "Videshi Chocolate Dabba",
        "tagline": "Duty-free chocolates and treats brought home", "category": "food_sealed", "max_weight_kg": 3.0,
        "candidates": [
            {"name": "Toblerone 360g", "unit": "bar", "approx_weight_kg": 0.36, "approx_value_inr": 1100},
            {"name": "Lindt Lindor assorted box", "unit": "box", "approx_weight_kg": 0.34, "approx_value_inr": 1600},
            {"name": "Ferrero Rocher 24 pcs", "unit": "box", "approx_weight_kg": 0.3, "approx_value_inr": 1400},
            {"name": "Kinder Bueno multipack", "unit": "pack", "approx_weight_kg": 0.3, "approx_value_inr": 700},
            {"name": "Dates with almonds (sealed)", "unit": "box", "approx_weight_kg": 0.5, "approx_value_inr": 1200},
        ],
    },
    {
        "id": "videshi-beauty", "kind": "videshi", "emoji": "💄", "name": "Videshi Beauty Dabba",
        "tagline": "Skincare and fragrance at overseas prices", "category": "gifts", "max_weight_kg": 2.0,
        "candidates": [
            {"name": "Sunscreen SPF50 (sealed, <100ml)", "unit": "tube", "approx_weight_kg": 0.1, "approx_value_inr": 1500},
            {"name": "Sheet mask pack (10)", "unit": "pack", "approx_weight_kg": 0.25, "approx_value_inr": 1200},
            {"name": "Perfume 100ml (sealed)", "unit": "bottle", "approx_weight_kg": 0.4, "approx_value_inr": 6500},
            {"name": "Lip balm set", "unit": "set", "approx_weight_kg": 0.1, "approx_value_inr": 900},
            {"name": "Moisturiser 50ml", "unit": "jar", "approx_weight_kg": 0.15, "approx_value_inr": 2200},
        ],
    },
    {
        "id": "videshi-tech", "kind": "videshi", "emoji": "🎧", "name": "Videshi Gadget Dabba",
        "tagline": "Accessories that cost more in India", "category": "electronics_small", "max_weight_kg": 2.0,
        "candidates": [
            {"name": "Wireless earbuds", "unit": "piece", "approx_weight_kg": 0.15, "approx_value_inr": 12000},
            {"name": "USB-C GaN charger", "unit": "piece", "approx_weight_kg": 0.2, "approx_value_inr": 3500},
            {"name": "Smart tracker tag (4 pack)", "unit": "pack", "approx_weight_kg": 0.1, "approx_value_inr": 8500},
            {"name": "Kindle e-reader", "unit": "piece", "approx_weight_kg": 0.25, "approx_value_inr": 11000},
        ],
    },
]

DABBA_BY_ID = {d["id"]: d for d in DABBAS}
