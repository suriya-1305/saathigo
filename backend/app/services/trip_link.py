"""Resolve the trip a traveller uses to carry/bring an order.

With BOARDING_PASS_ENABLED=false (default) a traveller does not have to create or verify a trip first:
taking an order reuses a matching active trip or records a lightweight one automatically.
"""
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.data.countries import country_name
from app.models import Trip, TripStatus, User


def resolve_trip(db: Session, user: User, *, origin_country: str, origin_city: str, destination_country: str,
                 destination_city: str, trip_id: int | None, travel_date: date | None,
                 needed_by: date | None, weight_kg: float | None = None) -> Trip:
    if trip_id:
        trip = db.get(Trip, trip_id)
        if not trip or trip.traveller_id != user.id or trip.status != TripStatus.ACTIVE:
            raise HTTPException(400, "Select one of your active trips")
        if trip.origin_country != origin_country or trip.destination_country != destination_country:
            raise HTTPException(400, f"Your trip must go from {country_name(origin_country)} to "
                                     f"{country_name(destination_country)}")
    else:
        trip = db.scalar(select(Trip).where(
            Trip.traveller_id == user.id, Trip.status == TripStatus.ACTIVE, Trip.origin_country == origin_country,
            Trip.destination_country == destination_country, Trip.travel_date >= date.today(),
        ).order_by(Trip.travel_date))
        if trip is None:
            if settings.boarding_pass_enabled:
                raise HTTPException(403, "Add and verify a trip on this route first")
            when = travel_date or needed_by or date.today() + timedelta(days=7)
            trip = Trip(traveller_id=user.id, origin_city=origin_city, origin_country=origin_country,
                        destination_city=destination_city, destination_country=destination_country,
                        travel_date=max(when, date.today()), capacity_kg=max(5.0, weight_kg or 0),
                        notes="Added automatically when taking an order")
            db.add(trip)
            db.flush()
    if settings.boarding_pass_enabled and not trip.verified:
        raise HTTPException(403, "Verify this trip by scanning your boarding pass first")
    if weight_kg and weight_kg > trip.capacity_kg:
        raise HTTPException(400, "Item exceeds your declared spare capacity")
    return trip
