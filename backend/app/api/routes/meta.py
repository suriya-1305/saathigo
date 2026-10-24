from fastapi import APIRouter

from app.core.config import settings
from app.data.countries import COUNTRIES, FX_TO_INR
from app.schemas import SHIPMENT_CATEGORIES

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/config")
def config():
    return {
        "app_name": settings.app_name,
        "countries": [{"code": c, **v} for c, v in COUNTRIES.items()],
        "currencies": sorted(FX_TO_INR),
        "fx_to_inr": FX_TO_INR,
        "shipment_categories": SHIPMENT_CATEGORIES,
        "traveller_reward_pct": settings.traveller_reward_pct,
        "platform_fee_pct": settings.platform_fee_pct,
        "boarding_pass_enabled": settings.boarding_pass_enabled,
        "payment_provider": settings.payment_provider,
    }
