from app.services.pricing import buy_pricing, send_pricing
from app.services.shipping.rate_card import RateCardEstimator


def test_rate_card_uses_volumetric_weight():
    est = RateCardEstimator()
    light = est.estimate(origin_city="Bengaluru", destination_country="US", weight_kg=1,
                         length_cm=0, width_cm=0, height_cm=0, declared_value_paise=0)
    bulky = est.estimate(origin_city="Bengaluru", destination_country="US", weight_kg=1,
                         length_cm=40, width_cm=30, height_cm=20, declared_value_paise=0)
    assert light.chargeable_weight_kg == 1.0
    assert bulky.chargeable_weight_kg == 5.0
    assert bulky.courier_cost_paise > light.courier_cost_paise


def test_send_pricing_is_value_based():
    p = send_pricing(1_000_000)  # Rs 10,000 product
    assert p.traveller_payout_paise == 200_000  # 20% to the traveller
    assert p.platform_fee_paise == 20_000       # 2% to SaathiGo
    assert p.price_paise == 220_000


def test_buy_pricing():
    p = buy_pricing(unit_price_paise=100_000, quantity=2)
    assert p.items_paise == 200_000
    assert p.reward_paise == 40_000
    assert p.service_fee_paise == 4_000
    assert p.total_paise == 244_000
    assert p.traveller_payout_paise == 240_000