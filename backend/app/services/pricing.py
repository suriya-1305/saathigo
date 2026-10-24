from dataclasses import dataclass

from app.core.config import settings


@dataclass
class SendPricing:
    value_paise: int
    price_paise: int            # what the sender pays
    traveller_payout_paise: int
    platform_fee_paise: int


@dataclass
class BuyPricing:
    items_paise: int
    reward_paise: int
    service_fee_paise: int
    total_paise: int
    traveller_payout_paise: int


def reward_for(value_paise: int) -> int:
    """Traveller earns TRAVELLER_REWARD_PCT (20%) of the product value."""
    return round(value_paise * settings.traveller_reward_pct)


def fee_for(value_paise: int) -> int:
    """SaathiGo keeps PLATFORM_FEE_PCT (2%) of the product value."""
    return round(value_paise * settings.platform_fee_pct)


def send_pricing(value_paise: int) -> SendPricing:
    """Sender pays 20% of the declared value to the traveller plus 2% to SaathiGo."""
    payout, fee = reward_for(value_paise), fee_for(value_paise)
    return SendPricing(value_paise, payout + fee, payout, fee)


def buy_pricing(unit_price_paise: int, quantity: int, reward_paise: int | None = None) -> BuyPricing:
    """Buyer pays the product + 20% traveller reward + 2% SaathiGo fee (both on the product value)."""
    items = unit_price_paise * quantity
    reward = reward_for(items) if reward_paise is None else reward_paise
    fee = fee_for(items)
    # Traveller is reimbursed for the item and receives the reward.
    return BuyPricing(items, reward, fee, items + reward + fee, items + reward)
