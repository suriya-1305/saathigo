from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator

from app.data.countries import COUNTRIES, FX_TO_INR


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- auth / users

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(ORM):
    id: int
    name: str
    email: str
    phone: str | None
    city: str | None
    upi_id: str | None
    is_admin: bool = False


class PublicUser(ORM):
    id: int
    name: str
    city: str | None


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=120)
    upi_id: str | None = Field(default=None, max_length=120)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------------------------------------------------------- trips

def _country(v: str) -> str:
    v = v.upper()
    if v not in COUNTRIES:
        raise ValueError("Unsupported country")
    return v


class BoardingPassScanOut(BaseModel):
    origin_code: str | None
    origin_city: str | None
    origin_country: str | None
    destination_code: str | None
    destination_city: str | None
    destination_country: str | None
    flight_number: str | None
    travel_date: date | None
    passenger_name: str | None
    score: int
    verified: bool
    checks: list[dict]
    scan_token: str | None
    message: str


class TripIn(BaseModel):
    origin_city: str = Field(min_length=2, max_length=120)
    origin_country: str
    destination_city: str = Field(min_length=2, max_length=120)
    destination_country: str
    travel_date: date
    flight_number: str | None = Field(default=None, max_length=10)
    capacity_kg: float = Field(default=5, gt=0, le=40)
    notes: str | None = Field(default=None, max_length=1000)
    scan_token: str | None = None

    _c1 = field_validator("origin_country", "destination_country")(_country)


class TripOut(ORM):
    id: int
    origin_code: str | None
    origin_city: str
    origin_country: str
    destination_code: str | None
    destination_city: str
    destination_country: str
    travel_date: date
    flight_number: str | None
    capacity_kg: float
    notes: str | None
    status: str
    verified: bool
    verification_score: int
    created_at: datetime


class VerifyTripIn(BaseModel):
    scan_token: str


# ---------------------------------------------------------------- buy from overseas

class LinkPreviewOut(BaseModel):
    url: str
    title: str | None
    description: str | None
    image_url: str | None
    price: float | None
    currency: str | None
    store_name: str | None
    source_country: str | None


class ProductRequestIn(BaseModel):
    product_url: HttpUrl
    title: str = Field(min_length=2, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    image_url: HttpUrl | None = None
    store_name: str | None = Field(default=None, max_length=120)
    quantity: int = Field(default=1, ge=1, le=10)
    price_amount: float = Field(gt=0, le=10_000_000)
    price_currency: str = Field(min_length=3, max_length=3)
    # Ignored: the traveller reward is always TRAVELLER_REWARD_PCT of the product value.
    reward_inr: int | None = Field(default=None, ge=0, le=1_000_000)
    source_country: str
    deliver_city: str = Field(min_length=2, max_length=120)
    needed_by: date | None = None

    _c = field_validator("source_country")(_country)

    @field_validator("price_currency")
    @classmethod
    def _currency(cls, v: str) -> str:
        v = v.upper()
        if v not in FX_TO_INR:
            raise ValueError("Unsupported currency")
        return v


class OfferIn(BaseModel):
    trip_id: int | None = None
    travel_date: date | None = None
    expected_delivery: date | None = None
    message: str | None = Field(default=None, max_length=1000)


class OfferOut(ORM):
    id: int
    request_id: int
    traveller: PublicUser
    trip: TripOut
    reward_paise: int
    expected_delivery: date | None
    message: str | None
    status: str
    created_at: datetime


class ProductRequestOut(BaseModel):
    id: int
    product_url: str
    title: str
    description: str | None
    image_url: str | None
    store_name: str | None
    quantity: int
    price_amount: float
    price_currency: str
    item_price_paise: int
    reward_paise: int
    service_fee_paise: int
    total_paise: int
    source_country: str
    source_country_name: str
    deliver_city: str
    needed_by: date | None
    status: str
    buyer: PublicUser
    traveller: PublicUser | None
    offers_count: int
    created_at: datetime
    # Visible only to involved parties
    offers: list[OfferOut] | None = None
    delivery_otp: str | None = None
    purchase_photo_url: str | None = None
    is_buyer: bool = False
    is_traveller: bool = False


class CountryGroup(BaseModel):
    country: str
    country_name: str
    count: int
    items: list


class DeliverIn(BaseModel):
    otp: str = Field(min_length=4, max_length=6)


# ---------------------------------------------------------------- send overseas

SHIPMENT_CATEGORIES = ["documents", "clothing", "food_sealed", "gifts", "books", "electronics_small",
                       "medicines_prescribed", "other"]


class ShipmentIn(BaseModel):
    """Simple listing: what, how much it is worth, from where to where. Everything else is optional."""
    item_name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    declared_value_inr: int = Field(ge=100, le=500_000, description="Product value; pricing is a share of it")
    pickup_city: str = Field(min_length=2, max_length=120)
    destination_country: str
    destination_city: str = Field(min_length=2, max_length=120)
    needed_by: date | None = None
    weight_kg: float | None = Field(default=None, gt=0, le=23)
    category: str | None = None
    recipient_name: str | None = Field(default=None, max_length=120)
    recipient_phone: str | None = Field(default=None, max_length=30)
    recipient_address: str | None = Field(default=None, max_length=1000)
    # Signed verdict from POST /agents/compliance; without it the server runs Saathi Compliance itself.
    compliance_token: str | None = Field(default=None, max_length=20000)
    compliance_ack: bool = False

    _c = field_validator("destination_country")(_country)

    @field_validator("category")
    @classmethod
    def _cat(cls, v: str | None) -> str | None:
        if v is not None and v not in SHIPMENT_CATEGORIES:
            raise ValueError("Unsupported category")
        return v


class AcceptShipmentIn(BaseModel):
    trip_id: int | None = None
    travel_date: date | None = None

class ShipmentOut(BaseModel):
    id: int
    item_name: str
    description: str | None
    category: str
    weight_kg: float
    length_cm: float
    width_cm: float
    height_cm: float
    declared_value_paise: int
    pickup_city: str
    destination_country: str
    destination_country_name: str
    destination_city: str
    needed_by: date | None
    shipping_provider: str
    courier_estimate_paise: int
    price_paise: int
    traveller_payout_paise: int
    status: str
    sender: PublicUser
    traveller: PublicUser | None
    trip: TripOut | None
    handover_photo_url: str | None
    handover_at: datetime | None
    delivery_photo_url: str | None
    delivered_at: datetime | None
    created_at: datetime
    compliance_status: str | None = None
    compliance_report: dict | None = None
    # Visible only to involved parties
    recipient_name: str | None = None
    recipient_phone: str | None = None
    recipient_address: str | None = None
    delivery_otp: str | None = None
    platform_fee_paise: int | None = None
    is_sender: bool = False
    is_traveller: bool = False


# ---------------------------------------------------------------- payments

class CheckoutIn(BaseModel):
    purpose: str
    reference_id: int


class CheckoutOut(BaseModel):
    payment_id: int
    redirect_url: str
    provider: str


class PaymentOut(ORM):
    id: int
    purpose: str
    reference_id: int
    amount_paise: int
    currency: str
    provider: str
    status: str
    provider_order_id: str | None
    created_at: datetime


class PayoutOut(ORM):
    id: int
    purpose: str
    reference_id: int
    amount_paise: int
    status: str
    created_at: datetime
