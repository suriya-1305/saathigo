from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(120))
    upi_id: Mapped[str | None] = mapped_column(String(120))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)


class TripStatus:
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Trip(TimestampMixin, Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(primary_key=True)
    traveller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    origin_code: Mapped[str | None] = mapped_column(String(3))
    origin_city: Mapped[str] = mapped_column(String(120))
    origin_country: Mapped[str] = mapped_column(String(2), index=True)
    destination_code: Mapped[str | None] = mapped_column(String(3))
    destination_city: Mapped[str] = mapped_column(String(120))
    destination_country: Mapped[str] = mapped_column(String(2), index=True)
    travel_date: Mapped[date] = mapped_column(Date)
    flight_number: Mapped[str | None] = mapped_column(String(10))
    capacity_kg: Mapped[float] = mapped_column(Float, default=5.0)
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=TripStatus.ACTIVE)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_score: Mapped[int] = mapped_column(Integer, default=0)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # SHA-256 of the boarding pass bytes; the image itself is never stored.
    boarding_pass_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)

    traveller: Mapped[User] = relationship()


class RequestStatus:
    OPEN = "open"            # visible to travellers, accepting offers
    ACCEPTED = "accepted"    # buyer accepted an offer, awaiting payment
    PAID = "paid"            # funds held in escrow
    PURCHASED = "purchased"  # traveller bought the item (photo proof)
    DELIVERED = "delivered"  # buyer confirmed with OTP, payout released
    CANCELLED = "cancelled"


class ProductRequest(TimestampMixin, Base):
    __tablename__ = "product_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_url: Mapped[str] = mapped_column(String(2048))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(2048))
    store_name: Mapped[str | None] = mapped_column(String(120))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    price_amount: Mapped[float] = mapped_column(Float)
    price_currency: Mapped[str] = mapped_column(String(3))
    item_price_paise: Mapped[int] = mapped_column(Integer)  # unit price in INR paise
    reward_paise: Mapped[int] = mapped_column(Integer)       # traveller reward
    source_country: Mapped[str] = mapped_column(String(2), index=True)
    deliver_city: Mapped[str] = mapped_column(String(120))
    needed_by: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default=RequestStatus.OPEN, index=True)
    traveller_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    accepted_offer_id: Mapped[int | None] = mapped_column(Integer)
    service_fee_paise: Mapped[int] = mapped_column(Integer, default=0)
    total_paise: Mapped[int] = mapped_column(Integer, default=0)
    delivery_otp: Mapped[str | None] = mapped_column(String(6))
    purchase_photo: Mapped[str | None] = mapped_column(String(255))
    purchased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    buyer: Mapped[User] = relationship(foreign_keys=[buyer_id])
    traveller: Mapped[User | None] = relationship(foreign_keys=[traveller_id])
    offers: Mapped[list["Offer"]] = relationship(back_populates="request", order_by="Offer.created_at")


class OfferStatus:
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class Offer(TimestampMixin, Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("product_requests.id"), index=True)
    traveller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"))
    reward_paise: Mapped[int] = mapped_column(Integer)
    expected_delivery: Mapped[date | None] = mapped_column(Date)
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=OfferStatus.PENDING)

    request: Mapped[ProductRequest] = relationship(back_populates="offers")
    traveller: Mapped[User] = relationship()
    trip: Mapped[Trip] = relationship()


class ShipmentStatus:
    OPEN = "open"                # waiting for a traveller
    MATCHED = "matched"          # traveller accepted, awaiting sender payment
    PAID = "paid"                # escrowed, ready for handover
    IN_TRANSIT = "in_transit"    # traveller captured item photo at handover
    DELIVERED = "delivered"      # recipient OTP verified, payout released
    CANCELLED = "cancelled"


class Shipment(TimestampMixin, Base):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    item_name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50))
    weight_kg: Mapped[float] = mapped_column(Float)
    length_cm: Mapped[float] = mapped_column(Float, default=0)
    width_cm: Mapped[float] = mapped_column(Float, default=0)
    height_cm: Mapped[float] = mapped_column(Float, default=0)
    declared_value_paise: Mapped[int] = mapped_column(Integer, default=0)
    pickup_city: Mapped[str] = mapped_column(String(120))
    destination_country: Mapped[str] = mapped_column(String(2), index=True)
    destination_city: Mapped[str] = mapped_column(String(120))
    recipient_name: Mapped[str] = mapped_column(String(120))
    recipient_phone: Mapped[str] = mapped_column(String(30))
    recipient_address: Mapped[str] = mapped_column(Text)
    needed_by: Mapped[date | None] = mapped_column(Date)

    shipping_provider: Mapped[str] = mapped_column(String(40))
    courier_estimate_paise: Mapped[int] = mapped_column(Integer)
    price_paise: Mapped[int] = mapped_column(Integer)
    traveller_payout_paise: Mapped[int] = mapped_column(Integer)
    platform_fee_paise: Mapped[int] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String(20), default=ShipmentStatus.OPEN, index=True)
    traveller_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id"))
    handover_photo: Mapped[str | None] = mapped_column(String(255))
    handover_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_photo: Mapped[str | None] = mapped_column(String(255))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_otp: Mapped[str | None] = mapped_column(String(6))
    # Saathi Compliance verdict: clear | needs_review | blocked; report is the per-item JSON
    compliance_status: Mapped[str | None] = mapped_column(String(20))
    compliance_report: Mapped[str | None] = mapped_column(Text)

    sender: Mapped[User] = relationship(foreign_keys=[sender_id])
    traveller: Mapped[User | None] = relationship(foreign_keys=[traveller_id])
    trip: Mapped[Trip | None] = relationship()


class PaymentPurpose:
    PRODUCT_REQUEST = "product_request"
    SHIPMENT = "shipment"


class PaymentStatus:
    CREATED = "created"
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(30))
    reference_id: Mapped[int] = mapped_column(Integer, index=True)
    amount_paise: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    provider: Mapped[str] = mapped_column(String(20))
    merchant_order_reference: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    provider_order_id: Mapped[str | None] = mapped_column(String(100), index=True)
    redirect_url: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[str] = mapped_column(String(20), default=PaymentStatus.CREATED)
    raw_response: Mapped[str | None] = mapped_column(Text)


class PayoutStatus:
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"


class Payout(TimestampMixin, Base):
    __tablename__ = "payouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    traveller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(30))
    reference_id: Mapped[int] = mapped_column(Integer)
    amount_paise: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default=PayoutStatus.PENDING)
    provider_reference: Mapped[str | None] = mapped_column(String(100))


class AgentRun(Base):
    """Audit log of every Saathi agent call; needs_human rows form the human-review queue."""
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    agent: Mapped[str] = mapped_column(String(40), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(20))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(20))  # agenticorg | fallback
    status: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[float | None] = mapped_column(Float)
    needs_human: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    summary: Mapped[str] = mapped_column(String(500), default="")
    output: Mapped[str | None] = mapped_column(Text)
    run_id: Mapped[str | None] = mapped_column(String(64))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
