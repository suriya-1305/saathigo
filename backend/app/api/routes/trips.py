from datetime import UTC, date, datetime

import jwt
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.serializers import request_out, shipment_out
from app.core.config import settings
from app.core.deps import get_current_user
from app.core.security import create_token, decode_token
from app.data.airports import AIRPORTS
from app.db import get_db
from app.models import ProductRequest, RequestStatus, Shipment, ShipmentStatus, Trip, TripStatus, User
from app.schemas import BoardingPassScanOut, TripIn, TripOut, VerifyTripIn
from app.services import boarding_pass as bp
from app.services.storage import read_limited

router = APIRouter(prefix="/trips", tags=["trips"])

SCAN_TOKEN_TYPE = "bp_scan"
ALLOWED_BP_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "application/pdf"}


def _require_boarding_pass_feature() -> None:
    if not settings.boarding_pass_enabled:
        raise HTTPException(404, "Boarding pass scanning is turned off")


@router.post("/scan-boarding-pass", response_model=BoardingPassScanOut)
async def scan_boarding_pass(file: UploadFile = File(...), user: User = Depends(get_current_user),
                             db: Session = Depends(get_db)):
    """OCR a boarding pass in memory. The file is never written to disk or stored."""
    _require_boarding_pass_feature()
    if file.content_type and file.content_type not in ALLOWED_BP_TYPES:
        raise HTTPException(415, "Upload a JPG/PNG/WEBP photo or PDF of your boarding pass")
    content = await read_limited(file)
    try:
        fp = bp.fingerprint(content)
        try:
            text = bp.extract_text(content, file.content_type, file.filename)
        except bp.OcrUnavailableError as exc:
            raise HTTPException(503, str(exc))
        except bp.UnreadableFileError as exc:
            raise HTTPException(400, str(exc))
    finally:
        # Drop every reference to the uploaded bytes immediately.
        del content
        await file.close()

    data = bp.parse_boarding_pass_text(text)
    del text
    result = bp.verify(data, user.name)

    reused = db.scalar(select(Trip).where(Trip.boarding_pass_fingerprint == fp, Trip.traveller_id != user.id))
    if reused:
        result.score = 0
        result.checks.append({"label": "Boarding pass not used by another account", "ok": False})

    verified = result.score >= settings.boarding_pass_min_score
    origin, dest = data.origin, data.destination
    token = None
    if origin and dest:
        token = create_token(user.id, SCAN_TOKEN_TYPE, expires_minutes=30, extra={
            "fp": fp, "origin": data.origin_code, "destination": data.destination_code,
            "flight": data.flight_number, "date": data.travel_date.isoformat() if data.travel_date else None,
            "score": result.score,
        })
    if not (origin and dest):
        message = "We couldn't read the route. Try a clearer, well-lit photo or the PDF boarding pass."
    elif verified:
        message = "Boarding pass verified. The file has been discarded; only your route was kept."
    else:
        message = "Route detected but verification is incomplete. Check the details or rescan."

    return BoardingPassScanOut(
        origin_code=data.origin_code, origin_city=origin[0] if origin else None,
        origin_country=origin[1] if origin else None,
        destination_code=data.destination_code, destination_city=dest[0] if dest else None,
        destination_country=dest[1] if dest else None,
        flight_number=data.flight_number, travel_date=data.travel_date, passenger_name=data.passenger_name,
        score=result.score, verified=verified, checks=result.checks, scan_token=token, message=message,
    )


def _apply_scan_token(db: Session, trip: Trip, token: str, user: User) -> None:
    try:
        claims = decode_token(token, SCAN_TOKEN_TYPE)
    except jwt.PyJWTError:
        raise HTTPException(400, "Boarding pass scan expired. Please scan again.")
    if claims["sub"] != str(user.id):
        raise HTTPException(403, "Scan belongs to another user")
    other = db.scalar(select(Trip).where(Trip.boarding_pass_fingerprint == claims["fp"],
                                         Trip.traveller_id != user.id))
    if other:
        raise HTTPException(409, "This boarding pass is already linked to another account")

    origin, dest = AIRPORTS[claims["origin"]], AIRPORTS[claims["destination"]]
    trip.origin_code, trip.origin_city, trip.origin_country = claims["origin"], origin[0], origin[1]
    trip.destination_code, trip.destination_city, trip.destination_country = claims["destination"], dest[0], dest[1]
    if claims.get("date"):
        trip.travel_date = date.fromisoformat(claims["date"])
    if claims.get("flight"):
        trip.flight_number = claims["flight"]
    trip.verification_score = int(claims["score"])
    trip.verified = trip.verification_score >= settings.boarding_pass_min_score
    trip.verified_at = datetime.now(UTC) if trip.verified else None
    trip.boarding_pass_fingerprint = claims["fp"]


@router.post("", response_model=TripOut, status_code=201)
def create_trip(body: TripIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.origin_country == body.destination_country:
        raise HTTPException(400, "Origin and destination countries must differ")
    if body.origin_country != "IN" and body.destination_country != "IN":
        raise HTTPException(400, "Trips must start or end in India")
    trip = Trip(traveller_id=user.id, **body.model_dump(exclude={"scan_token"}))
    if body.scan_token and settings.boarding_pass_enabled:
        _apply_scan_token(db, trip, body.scan_token, user)
    db.add(trip)
    db.commit()
    return trip


@router.get("/mine", response_model=list[TripOut])
def my_trips(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Trip).where(Trip.traveller_id == user.id).order_by(Trip.travel_date.desc())).all()


def _own_trip(db: Session, trip_id: int, user: User) -> Trip:
    trip = db.get(Trip, trip_id)
    if not trip or trip.traveller_id != user.id:
        raise HTTPException(404, "Trip not found")
    return trip


@router.post("/{trip_id}/verify", response_model=TripOut)
def verify_trip(trip_id: int, body: VerifyTripIn, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    _require_boarding_pass_feature()
    trip = _own_trip(db, trip_id, user)
    _apply_scan_token(db, trip, body.scan_token, user)
    db.commit()
    return trip


@router.post("/{trip_id}/cancel", response_model=TripOut)
def cancel_trip(trip_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    trip = _own_trip(db, trip_id, user)
    active = db.scalar(select(Shipment).where(
        Shipment.trip_id == trip.id,
        Shipment.status.in_([ShipmentStatus.MATCHED, ShipmentStatus.PAID, ShipmentStatus.IN_TRANSIT])))
    if active:
        raise HTTPException(409, "You are carrying shipments on this trip")
    trip.status = TripStatus.CANCELLED
    db.commit()
    return trip


@router.get("/{trip_id}/matches")
def trip_matches(trip_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Buy requests from the trip's origin country (into India) and shipments to its destination (from India)."""
    trip = _own_trip(db, trip_id, user)
    requests: list = []
    shipments: list = []
    if trip.destination_country == "IN":
        rows = db.scalars(select(ProductRequest).where(
            ProductRequest.source_country == trip.origin_country,
            ProductRequest.status == RequestStatus.OPEN,
            ProductRequest.buyer_id != user.id,
        ).order_by(ProductRequest.created_at.desc()).limit(100)).all()
        requests = [request_out(r, user) for r in rows]
    if trip.origin_country == "IN":
        rows = db.scalars(select(Shipment).where(
            Shipment.destination_country == trip.destination_country,
            Shipment.status == ShipmentStatus.OPEN,
            Shipment.sender_id != user.id,
            Shipment.weight_kg <= trip.capacity_kg,
        ).order_by(Shipment.created_at.desc()).limit(100)).all()
        shipments = [shipment_out(s, user) for s in rows]
    return {"trip": TripOut.model_validate(trip), "requests": requests, "shipments": shipments}
