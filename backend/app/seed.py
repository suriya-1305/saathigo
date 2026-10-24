"""Demo data: senders, buyers and travellers with open parcels, product requests and trips.

Run from backend/:  python -m app.seed
Idempotent - existing users/listings (matched by email / title) are left untouched. Password for every
demo account: secret123
"""
from datetime import date, timedelta

from sqlalchemy import select

from app.core.security import hash_password
from app.data.countries import country_name, to_inr_paise
from app.db import Base, SessionLocal, engine
from app.models import (
    Offer, OfferStatus, ProductRequest, RequestStatus, Shipment, ShipmentStatus, Trip, TripStatus, User,
)
from app.services.agents import saathi
from app.services.agents import shipment_items
from app.services.pricing import buy_pricing, send_pricing

PASSWORD = "secret123"
D = lambda days: date.today() + timedelta(days=days)  # noqa: E731

USERS = [
    # name, email, city, role note
    ("Priya Sharma", "priya@example.com", "Pune"),        # sender + buyer
    ("Rahul Verma", "rahul@example.com", "Delhi"),        # sender + buyer
    ("Meera Iyer", "meera@example.com", "Chennai"),       # sender + buyer
    ("Anita Desai", "anita@example.com", "Ahmedabad"),    # sender + buyer
    ("Karan Mehta", "karan@example.com", "Mumbai"),       # traveller
    ("Neha Kapoor", "neha@example.com", "Bengaluru"),     # traveller
    ("Arjun Nair", "arjun@example.com", "Kochi"),         # traveller
    ("Sana Khan", "sana@example.com", "Hyderabad"),       # traveller
]

# sender, item, description, value INR, pickup, country, city, needed_by (days from today)
SHIPMENTS = [
    ("priya", "Homemade besan laddoos", "1 kg box, sealed", 1200, "Pune", "AE", "Dubai", 12),
    ("priya", "Silk saree for sister's wedding", None, 8500, "Pune", "GB", "London", 20),
    ("rahul", "Diwali dry-fruit gift hamper", "Almonds, cashews, raisins - sealed retail packs", 3500,
     "Delhi", "CA", "Toronto", 18),
    ("rahul", "University documents", "Sealed envelope with degree certificates", 500, "Delhi", "US",
     "New York", 10),
    ("meera", "Kanjeevaram saree and blouse", None, 15000, "Chennai", "SG", "Singapore", 14),
    ("meera", "Ayurvedic hair oil and herbal soaps", "2 bottles oil, 6 soaps", 1800, "Chennai", "AU",
     "Sydney", 25),
    ("anita", "Kids ethnic wear (2 sets)", None, 4000, "Ahmedabad", "AE", "Abu Dhabi", 9),
    ("anita", "Gujarati novels (3 books)", None, 900, "Ahmedabad", "US", "New York", 30),
    ("asha", "Rakhi and greeting cards", None, 700, "Bengaluru", "US", "San Francisco", 15),
]

# buyer, title, url, price, currency, country, deliver city, qty, needed_by
REQUESTS = [
    ("rahul", "Apple AirPods Pro (2nd gen)", "https://www.apple.com/ae/airpods-pro/", 899, "AED", "AE",
     "Delhi", 1, 21),
    ("priya", "MUJI ultrasonic aroma diffuser", "https://www.muji.com/jp/ja/store", 6990, "JPY", "JP", "Pune", 1,
     30),
    ("meera", "Dyson Airwrap multi-styler", "https://www.dyson.com.sg/hair-care/airwrap", 899, "SGD", "SG",
     "Chennai", 1, 25),
    ("anita", "Kiehl's Ultra Facial Cream 125 ml", "https://www.kiehls.com/skincare/moisturizers/", 70, "USD",
     "US", "Ahmedabad", 2, 28),
    ("asha", "Lindt Swiss chocolate assortment", "https://www.lindt.ch/en/", 39, "CHF", "CH", "Bengaluru", 2, 20),
    ("rahul", "Nike Air Max 90 (UK 9)", "https://www.nike.com/gb/w/air-max-90", 140, "GBP", "GB", "Delhi", 1, 24),
    ("anita", "Tim Hortons ground coffee (3 packs)", "https://www.timhortons.ca/", 25, "CAD", "CA", "Ahmedabad",
     3, 35),
]

# traveller, origin city, origin cc, dest city, dest cc, travel in days, capacity kg
TRIPS = [
    ("karan", "Mumbai", "IN", "Dubai", "AE", 6, 8),
    ("karan", "Dubai", "AE", "Mumbai", "IN", 19, 8),
    ("neha", "Bengaluru", "IN", "San Francisco", "US", 10, 10),
    ("neha", "London", "GB", "Bengaluru", "IN", 16, 6),
    ("arjun", "Kochi", "IN", "Singapore", "SG", 8, 7),
    ("arjun", "Singapore", "SG", "Kochi", "IN", 18, 7),
    ("sana", "Hyderabad", "IN", "Toronto", "CA", 12, 10),
]


def _user(db, name: str, email: str, city: str) -> User:
    u = db.scalar(select(User).where(User.email == email))
    if u is None:
        u = User(name=name, email=email, city=city, phone="9800000000", password_hash=hash_password(PASSWORD))
        db.add(u)
        db.flush()
    return u


def _compliance(item: str, description: str | None, country: str) -> dict:
    verdicts = [saathi._fallback_verdict(i) for i in shipment_items(item, description)]
    overall = saathi.compliance_overall(verdicts)
    return {"route": f"India -> {country_name(country)}", "items": verdicts, "overall": overall,
            "guidance": "Guidance based on common rules, not legal advice. The traveller declares items at customs.",
            "next_step": "Pack flagged items in sealed, labelled packaging." if overall != "clear" else
            "Ready for a traveller.",
            "meta": {"agent": "compliance", "source": "fallback", "confidence": None,
                     "needs_human": overall != "clear", "note": "Seed data", "latency_ms": 0}}


def seed() -> dict:
    import json

    Base.metadata.create_all(bind=engine)
    created = {"users": 0, "shipments": 0, "requests": 0, "trips": 0}
    with SessionLocal() as db:
        by_key: dict[str, User] = {}
        for name, email, city in USERS:
            existed = db.scalar(select(User).where(User.email == email)) is not None
            by_key[email.split("@")[0]] = _user(db, name, email, city)
            created["users"] += 0 if existed else 1
        by_key["asha"] = _user(db, "Asha", "asha@example.com", "Bengaluru")
        by_key["vik"] = _user(db, "Vikram", "vik@example.com", "Mumbai")

        for key, item, desc, value, pickup, cc, city, days in SHIPMENTS:
            u = by_key[key]
            if db.scalar(select(Shipment).where(Shipment.sender_id == u.id, Shipment.item_name == item)):
                continue
            p = send_pricing(value * 100)
            report = _compliance(item, desc, cc)
            db.add(Shipment(
                sender_id=u.id, item_name=item, description=desc,
                category=saathi._guess_category(f"{item} {desc or ''}"), weight_kg=0,
                declared_value_paise=p.value_paise, pickup_city=pickup, destination_country=cc,
                destination_city=city, recipient_name="", recipient_phone="", recipient_address="",
                needed_by=D(days), shipping_provider="value_based", courier_estimate_paise=0,
                price_paise=p.price_paise, traveller_payout_paise=p.traveller_payout_paise,
                platform_fee_paise=p.platform_fee_paise, compliance_status=report["overall"],
                compliance_report=json.dumps(report)))
            created["shipments"] += 1

        for key, title, url, price, cur, cc, city, qty, days in REQUESTS:
            u = by_key[key]
            if db.scalar(select(ProductRequest).where(ProductRequest.buyer_id == u.id,
                                                      ProductRequest.title == title)):
                continue
            unit = to_inr_paise(price, cur)
            p = buy_pricing(unit, qty)
            db.add(ProductRequest(
                buyer_id=u.id, product_url=url, title=title, quantity=qty, price_amount=price, price_currency=cur,
                item_price_paise=unit, reward_paise=p.reward_paise, service_fee_paise=p.service_fee_paise,
                total_paise=p.total_paise, source_country=cc, deliver_city=city, needed_by=D(days)))
            created["requests"] += 1

        trips: dict[tuple, Trip] = {}
        for key, ocity, occ, dcity, dcc, days, cap in TRIPS:
            u = by_key[key]
            t = db.scalar(select(Trip).where(Trip.traveller_id == u.id, Trip.origin_country == occ,
                                             Trip.destination_country == dcc, Trip.status == TripStatus.ACTIVE))
            if t is None:
                t = Trip(traveller_id=u.id, origin_city=ocity, origin_country=occ, destination_city=dcity,
                         destination_country=dcc, travel_date=D(days), capacity_kg=cap)
                db.add(t)
                db.flush()
                created["trips"] += 1
            trips[(key, occ, dcc)] = t

        # A couple of orders already in progress so dashboards and the Saathi popup have something to show
        neha_trip = trips[("neha", "GB", "IN")]
        laddoos = db.scalar(select(Shipment).where(Shipment.item_name == "Homemade besan laddoos"))
        if laddoos and laddoos.status == ShipmentStatus.OPEN:
            laddoos.traveller_id, laddoos.trip_id = by_key["karan"].id, trips[("karan", "IN", "AE")].id
            laddoos.status = ShipmentStatus.MATCHED
        airpods = db.scalar(select(ProductRequest).where(ProductRequest.title == "Apple AirPods Pro (2nd gen)"))
        if airpods and not airpods.offers:
            db.add(Offer(request_id=airpods.id, traveller_id=by_key["karan"].id,
                         trip_id=trips[("karan", "AE", "IN")].id, reward_paise=airpods.reward_paise,
                         expected_delivery=D(20), message="Flying back from Dubai, happy to bring it.",
                         status=OfferStatus.PENDING))
        nike = db.scalar(select(ProductRequest).where(ProductRequest.title == "Nike Air Max 90 (UK 9)"))
        if nike and not nike.offers and nike.status == RequestStatus.OPEN:
            db.add(Offer(request_id=nike.id, traveller_id=by_key["neha"].id, trip_id=neha_trip.id,
                         reward_paise=nike.reward_paise, expected_delivery=D(17),
                         message="I'm in London next week.", status=OfferStatus.PENDING))

        # Older listings were priced on courier cost; move open ones to value-based pricing
        for s in db.scalars(select(Shipment).where(Shipment.status == ShipmentStatus.OPEN,
                                                   Shipment.shipping_provider != "value_based")).all():
            p = send_pricing(s.declared_value_paise or 200_000)
            s.declared_value_paise, s.price_paise = p.value_paise, p.price_paise
            s.traveller_payout_paise, s.platform_fee_paise = p.traveller_payout_paise, p.platform_fee_paise
            s.shipping_provider, s.courier_estimate_paise = "value_based", 0
        for r in db.scalars(select(ProductRequest).where(ProductRequest.status == RequestStatus.OPEN)).all():
            p = buy_pricing(r.item_price_paise, r.quantity)
            r.reward_paise, r.service_fee_paise, r.total_paise = p.reward_paise, p.service_fee_paise, p.total_paise
        db.commit()
    return created


if __name__ == "__main__":
    out = seed()
    print(f"Seeded: {out}. Every demo account uses password '{PASSWORD}':")
    for name, email, city in USERS:
        print(f"  {email:<22} {name} ({city})")
