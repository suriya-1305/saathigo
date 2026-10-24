"""Saathi endpoints: every agent in the SaathiGo flow (Pine Labs AgenticOrg)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_optional_user
from app.data.countries import COUNTRIES, country_name
from app.data.dabbas import DABBA_BY_ID, DABBAS
from app.db import get_db
from app.models import (
    AgentRun, Offer, OfferStatus, Payout, ProductRequest, RequestStatus, Shipment, ShipmentStatus, Trip, TripStatus, User,
)
from app.services import agents
from app.services.agents import saathi
from app.services.pricing import send_pricing

router = APIRouter(prefix="/agents", tags=["saathi-agents"])


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=4000)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[Turn] = Field(default_factory=list, max_length=20)


class ComplianceIn(BaseModel):
    items: list[str] = Field(min_length=1, max_length=20)
    destination_country: str
    origin_country: str = "IN"


class CurateIn(BaseModel):
    country: str
    needed_by: date | None = None
    preferences: str | None = Field(default=None, max_length=500)


class NegotiateIn(BaseModel):
    request_id: int | None = None
    title: str | None = Field(default=None, max_length=300)
    item_value_inr: float | None = Field(default=None, ge=0)
    quantity: int = Field(default=1, ge=1, le=10)
    source_country: str | None = None
    needed_by: date | None = None
    proposed_reward_inr: int | None = Field(default=None, ge=0)


class SupportIn(BaseModel):
    kind: str = Field(pattern="^(shipment|request)$")
    id: int
    question: str = Field(min_length=2, max_length=1000)
    history: list[Turn] = Field(default_factory=list, max_length=12)


def _country(code: str) -> str:
    code = code.upper()
    if code not in COUNTRIES:
        raise HTTPException(400, "Unsupported country")
    return code


def _meta_list(*outcomes: saathi.Outcome) -> list[dict]:
    return [o.meta() for o in outcomes]


@router.get("/status")
def status():
    return {"enabled": settings.agents_enabled, "provider": "agenticorg" if settings.agents_enabled else "fallback",
            "agents": ["concierge", "intake", "dabba_curator", "compliance", "matching", "negotiation",
                       "tracking_support"]}


# ------------------------------------------------------------ concierge + intake

def _estimate_for(draft: dict) -> dict | None:
    if draft.get("kind") != "send" or not draft.get("declared_value_inr"):
        return None
    p = send_pricing(int(draft["declared_value_inr"]) * 100)
    return {"value_paise": p.value_paise, "price_paise": p.price_paise,
            "traveller_payout_paise": p.traveller_payout_paise, "platform_fee_paise": p.platform_fee_paise}


@router.post("/chat")
def chat(body: ChatIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Concierge replies and routes; Intake runs in parallel and turns the conversation into an order draft."""
    history = [t.model_dump() for t in body.history]
    guess = saathi._guess_intent(" ".join([*(t["content"] for t in history if t["role"] == "user"), body.message]))
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_con = pool.submit(saathi.concierge, body.message, history)
        f_int = pool.submit(saathi.intake, body.message, history, guess) \
            if guess in ("send_abroad", "buy_from_abroad") else None
        con = f_con.result()
        intake = f_int.result() if f_int else None
    intent = con.data["intent"]
    if intent in ("send_abroad", "buy_from_abroad") and (
            intake is None or (intent == "buy_from_abroad") != (intake.data.get("kind") == "buy")):
        intake = saathi.intake(body.message, history, intent)
    if intent not in ("send_abroad", "buy_from_abroad") and guess not in ("send_abroad", "buy_from_abroad"):
        intake = None

    agents.log_run(db, con, user.id, f"Intent: {intent} - {body.message[:120]}")
    draft = None
    if intake is not None:
        draft = intake.data
        agents.log_run(db, intake, user.id, f"Draft {draft.get('kind')} order; missing: "
                                             f"{', '.join(draft.get('missing_fields') or []) or 'none'}")
    db.commit()
    return {"reply": con.data["reply"], "intent": intent, "draft": draft,
            "estimate": _estimate_for(draft) if draft else None,
            "agents": _meta_list(*(o for o in (con, intake) if o))}


# ------------------------------------------------------------ compliance

@router.post("/compliance")
def compliance(body: ComplianceIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dest, origin = _country(body.destination_country), _country(body.origin_country)
    items = [i for i in body.items if i.strip()]
    if not items:
        raise HTTPException(400, "Add at least one item")
    outcome = saathi.check_compliance(items, origin, dest)
    agents.log_run(db, outcome, user.id, f"Compliance {origin}->{dest}: {outcome.data['overall']}")
    db.commit()
    return {"report": {**outcome.data, "meta": outcome.meta()},
            "token": agents.issue_compliance_token(user.id, items, dest, outcome) if origin == "IN" else None}


# ------------------------------------------------------------ dabbas

@router.get("/dabbas")
def list_dabbas():
    return DABBAS


@router.post("/dabbas/{dabba_id}/curate")
def curate(dabba_id: str, body: CurateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    dabba = DABBA_BY_ID.get(dabba_id)
    if not dabba:
        raise HTTPException(404, "Dabba not found")
    country = _country(body.country)
    if country == "IN":
        raise HTTPException(400, "Pick the country abroad")
    outcome = saathi.curate_dabba(dabba, country, body.needed_by, body.preferences)
    box = outcome.data
    lines = "\n".join(f"- {i['quantity']} {i['unit']} {i['name']}" for i in box["items"])
    if dabba["kind"] == "swadeshi":
        draft = {"kind": "send", "item_name": box["name"], "description": lines, "category": box["category"],
                 "destination_country": country, "weight_kg": max(0.1, box["total_weight_kg"]),
                 "declared_value_inr": box["total_value_inr"], "needed_by": body.needed_by}
    else:
        draft = {"kind": "buy", "title": box["name"], "description": lines, "source_country": country,
                 "product_url": f"{settings.frontend_url.rstrip('/')}/dabbas#{dabba['id']}",
                 "price_amount": box["total_value_inr"], "price_currency": "INR", "needed_by": body.needed_by}
    agents.log_run(db, outcome, user.id, f"Curated {box['name']} for {country_name(country)}: "
                                         f"{len(box['items'])} items")
    db.commit()
    return {"box": box, "draft": draft, "agent": outcome.meta()}


# ------------------------------------------------------------ matching

def _deliveries(db: Session, user_ids: set[int]) -> dict[int, int]:
    if not user_ids:
        return {}
    rows = db.execute(select(Payout.traveller_id, func.count()).where(Payout.traveller_id.in_(user_ids))
                      .group_by(Payout.traveller_id)).all()
    return {uid: n for uid, n in rows}


def _rank_trips(db: Session, trips: list[Trip], needed_by: date | None, weight: float | None, purpose: str,
                subject: dict) -> tuple[list[dict], saathi.Outcome]:
    done = _deliveries(db, {t.traveller_id for t in trips})
    info = {t.id: t for t in trips}
    candidates = [{
        "id": t.id, "route": f"{t.origin_city} ({t.origin_country}) -> {t.destination_city} ({t.destination_country})",
        "travel_date": t.travel_date.isoformat(), "spare_kg": t.capacity_kg,
        "boarding_pass_score": t.verification_score, "completed_deliveries": done.get(t.traveller_id, 0),
    } for t in trips]

    def score(c: dict) -> tuple[int, str]:
        s, why = saathi.date_fit_score(date.fromisoformat(c["travel_date"]), needed_by)
        s = min(100, s + min(10, c["completed_deliveries"] * 2) + (5 if c["boarding_pass_score"] >= 80 else 0))
        if weight and c["spare_kg"] >= weight * 2:
            s, why = min(100, s + 5), why + "; plenty of spare capacity"
        return s, why

    outcome = saathi.rank_candidates(purpose, subject, candidates, score)
    ranked = []
    for r in outcome.data["ranked"]:
        t = info[r["id"]]
        ranked.append({**r, "trip": {"id": t.id, "origin_city": t.origin_city, "destination_city": t.destination_city,
                                     "travel_date": t.travel_date, "flight_number": t.flight_number,
                                     "capacity_kg": t.capacity_kg, "verification_score": t.verification_score},
                       "traveller": {"id": t.traveller.id, "name": t.traveller.name, "city": t.traveller.city,
                                     "completed_deliveries": done.get(t.traveller_id, 0)}})
    return ranked, outcome


def _eligible_trips(db: Session, origin: str, dest: str, exclude_user: int, needed_by: date | None,
                    weight: float | None) -> list[Trip]:
    q = select(Trip).where(Trip.origin_country == origin, Trip.destination_country == dest,
                           Trip.status == TripStatus.ACTIVE,
                           Trip.travel_date >= date.today(), Trip.traveller_id != exclude_user)
    if settings.boarding_pass_enabled:
        q = q.where(Trip.verified.is_(True))
    if needed_by:
        q = q.where(Trip.travel_date <= needed_by)
    if weight:
        q = q.where(Trip.capacity_kg >= weight)
    return list(db.scalars(q.order_by(Trip.travel_date).limit(15)).all())


@router.get("/shipments/{shipment_id}/travellers")
def shipment_travellers(shipment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    shp = db.get(Shipment, shipment_id)
    if not shp or shp.sender_id != user.id:
        raise HTTPException(404, "Shipment not found")
    trips = _eligible_trips(db, "IN", shp.destination_country, user.id, shp.needed_by, shp.weight_kg)
    ranked, outcome = _rank_trips(
        db, trips, shp.needed_by, shp.weight_kg, "Rank travellers to carry a parcel from India.",
        {"route": f"India -> {shp.destination_city}, {country_name(shp.destination_country)}",
         "weight_kg": shp.weight_kg, "needed_by": shp.needed_by, "category": shp.category})
    if trips:
        agents.log_run(db, outcome, user.id, f"Ranked {len(ranked)} travellers", "shipment", shp.id)
        db.commit()
    return {"ranked": ranked, "excluded": outcome.data["excluded"], "agent": outcome.meta()}


@router.get("/requests/{request_id}/travellers")
def request_travellers(request_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = db.get(ProductRequest, request_id)
    if not req or req.buyer_id != user.id:
        raise HTTPException(404, "Request not found")
    trips = _eligible_trips(db, req.source_country, "IN", user.id, req.needed_by, None)
    ranked, outcome = _rank_trips(
        db, trips, req.needed_by, None, f"Rank travellers to bring a product from {country_name(req.source_country)}"
                                        " to India.",
        {"product": req.title, "quantity": req.quantity, "deliver_city": req.deliver_city,
         "needed_by": req.needed_by})
    if trips:
        agents.log_run(db, outcome, user.id, f"Ranked {len(ranked)} travellers", "request", req.id)
        db.commit()
    return {"ranked": ranked, "excluded": outcome.data["excluded"], "agent": outcome.meta()}


@router.get("/trips/{trip_id}/opportunities")
def trip_opportunities(trip_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Saathi Matching ranks the open orders on a traveller's route."""
    trip = db.get(Trip, trip_id)
    if not trip or trip.traveller_id != user.id:
        raise HTTPException(404, "Trip not found")
    pool: list[tuple[str, object]] = []
    if trip.destination_country == "IN":
        pool += [("request", r) for r in db.scalars(select(ProductRequest).where(
            ProductRequest.source_country == trip.origin_country, ProductRequest.status == RequestStatus.OPEN,
            ProductRequest.buyer_id != user.id).limit(15)).all()]
    if trip.origin_country == "IN":
        pool += [("shipment", s) for s in db.scalars(select(Shipment).where(
            Shipment.destination_country == trip.destination_country, Shipment.status == ShipmentStatus.OPEN,
            Shipment.sender_id != user.id, Shipment.weight_kg <= trip.capacity_kg).limit(15)).all()]
    candidates = []
    for idx, (kind, obj) in enumerate(pool, 1):
        if kind == "request":
            candidates.append({"id": idx, "kind": "buy request", "title": obj.title, "needed_by": obj.needed_by,
                               "reward_inr": obj.reward_paise // 100, "deliver_city": obj.deliver_city})
        else:
            candidates.append({"id": idx, "kind": "parcel", "title": obj.item_name, "needed_by": obj.needed_by,
                               "reward_inr": obj.traveller_payout_paise // 100, "weight_kg": obj.weight_kg,
                               "destination_city": obj.destination_city, "compliance": obj.compliance_status})

    def score(c: dict) -> tuple[int, str]:
        s, why = saathi.date_fit_score(trip.travel_date, c["needed_by"])
        if c.get("compliance") == "needs_review":
            s -= 10
            why += "; packaging check pending"
        return max(0, min(100, s + min(15, c["reward_inr"] // 200))), why + f"; reward Rs {c['reward_inr']}"

    outcome = saathi.rank_candidates(
        "You are ranking open orders for ONE traveller (the candidates are orders, not travellers). Prefer orders "
        "whose needed_by is on/after the traveller's arrival, higher reward per kg, and cleared compliance.",
        {"traveller_trip": f"{trip.origin_city} -> {trip.destination_city}", "travel_date": trip.travel_date,
         "spare_kg": trip.capacity_kg}, candidates, score)
    ranked = []
    for r in outcome.data["ranked"]:
        kind, obj = pool[r["id"] - 1]
        ranked.append({"score": r["score"], "reason": r["reason"], "kind": kind, "id": obj.id,
                       "title": candidates[r["id"] - 1]["title"], "reward_inr": candidates[r["id"] - 1]["reward_inr"]})
    if candidates:
        agents.log_run(db, outcome, user.id, f"Ranked {len(ranked)} orders for trip", "trip", trip.id)
        db.commit()
    return {"ranked": ranked, "agent": outcome.meta()}


# ------------------------------------------------------------ negotiation

@router.post("/negotiate")
def negotiate(body: NegotiateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    offers: list[dict] = []
    entity_id = None
    if body.request_id:
        req = db.get(ProductRequest, body.request_id)
        if not req:
            raise HTTPException(404, "Request not found")
        entity_id = req.id
        ctx = {"product": req.title, "quantity": req.quantity,
               "item_value_inr": req.item_price_paise * req.quantity / 100,
               "route": f"{country_name(req.source_country)} -> {req.deliver_city}, India",
               "needed_by": req.needed_by, "buyer_reward_inr": req.reward_paise // 100,
               "platform_fee_pct": settings.platform_fee_pct,
               "standard_reward_pct_of_value": settings.traveller_reward_pct}
        if user.id == req.buyer_id:
            offers = [{"offer_id": o.id, "reward_inr": o.reward_paise // 100, "expected_delivery": o.expected_delivery}
                      for o in req.offers if o.status == OfferStatus.PENDING]
        if body.proposed_reward_inr:
            ctx["traveller_proposed_reward_inr"] = body.proposed_reward_inr
    else:
        if not body.item_value_inr:
            raise HTTPException(400, "Provide request_id or item_value_inr")
        ctx = {"product": body.title or "item", "quantity": body.quantity,
               "item_value_inr": body.item_value_inr * body.quantity,
               "route": f"{country_name(_country(body.source_country))} -> India" if body.source_country else None,
               "needed_by": body.needed_by}
    outcome = saathi.suggest_reward(ctx, offers)
    agents.log_run(db, outcome, user.id, f"Suggested reward Rs {outcome.data['suggested_reward_inr']}",
                   "request" if entity_id else None, entity_id)
    db.commit()
    return {**outcome.data, "agent": outcome.meta()}


# ------------------------------------------------------------ tracking & support

def _order_snapshot(kind: str, obj, trip: Trip | None) -> dict:
    tl: list[dict] = [{"at": obj.created_at, "event": "order created"}]
    if kind == "shipment":
        if obj.traveller_id:
            tl.append({"at": obj.updated_at, "event": "verified traveller matched"})
        if obj.handover_at:
            tl.append({"at": obj.handover_at, "event": "handed over to traveller, photo captured"})
        if obj.delivered_at:
            tl.append({"at": obj.delivered_at, "event": "delivered, OTP verified"})
        route = f"{obj.pickup_city} -> {obj.destination_city}, {country_name(obj.destination_country)}"
        title = obj.item_name
    else:
        if obj.purchased_at:
            tl.append({"at": obj.purchased_at, "event": "traveller purchased item, photo uploaded"})
        if obj.delivered_at:
            tl.append({"at": obj.delivered_at, "event": "delivered, OTP verified"})
        route = f"{country_name(obj.source_country)} -> {obj.deliver_city}"
        title = obj.title
    return {"id": f"{'S' if kind == 'shipment' else 'R'}{obj.id}", "title": title, "route": route,
            "status": obj.status, "needed_by": obj.needed_by, "timeline": tl,
            "traveller_flight": (f"{trip.flight_number or ''} {trip.travel_date}".strip() if trip else None)}


@router.post("/support")
def support(body: SupportIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    obj = db.get(Shipment if body.kind == "shipment" else ProductRequest, body.id)
    owner = getattr(obj, "sender_id", None) if body.kind == "shipment" else getattr(obj, "buyer_id", None)
    if not obj or user.id not in (owner, obj.traveller_id):
        raise HTTPException(404, "Order not found")
    trip = obj.trip if body.kind == "shipment" else None
    if body.kind == "request" and obj.accepted_offer_id:
        accepted = next((o for o in obj.offers if o.id == obj.accepted_offer_id), None)
        trip = accepted.trip if accepted else None
    outcome = saathi.support(body.question, _order_snapshot(body.kind, obj, trip),
                             [t.model_dump() for t in body.history])
    agents.log_run(db, outcome, user.id, ("ESCALATED: " if outcome.data["escalate"] else "") + body.question[:200],
                   body.kind, obj.id)
    db.commit()
    return {**outcome.data, "agent": outcome.meta()}


# ------------------------------------------------------------ assistant popup

class AssistantIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[Turn] = Field(default_factory=list, max_length=12)


_NEXT = {
    ("shipment", "sender"): {"open": "Wait for a traveller to take it - it is visible to everyone flying there.",
                             "matched": "A traveller took it. Pay to confirm.",
                             "paid": "Hand the parcel to the traveller; they will photograph it.",
                             "in_transit": "Share the delivery OTP with your recipient."},
    ("shipment", "traveller"): {"matched": "Wait for the sender's payment.",
                                "paid": "Collect the parcel and capture the handover photo.",
                                "in_transit": "Deliver it and enter the recipient's OTP to get paid."},
    ("request", "buyer"): {"open": "Wait for offers from travellers and accept one.",
                           "accepted": "Pay to confirm the order.",
                           "paid": "The traveller will buy the item and upload a photo.",
                           "purchased": "Share your delivery OTP when you receive the item."},
    ("request", "traveller"): {"accepted": "Wait for the buyer's payment.",
                               "paid": "Buy the item and upload a photo of it.",
                               "purchased": "Deliver it and enter the buyer's OTP to get paid."},
}


def _inr(paise: int | None) -> int:
    return int((paise or 0) // 100)


def _assistant_context(db: Session, user: User | None, question: str) -> dict:
    ctx: dict = {"signed_in": user is not None, "my_orders": [],
                 "pricing": {"platform": settings.app_name,
                             "traveller_reward_pct": round(settings.traveller_reward_pct * 100),
                             "platform_fee_pct": round(settings.platform_fee_pct * 100)}}
    uid = user.id if user else -1
    if user:
        ctx["user_name"] = user.name
        for s in db.scalars(select(Shipment).where((Shipment.sender_id == uid) | (Shipment.traveller_id == uid))
                            .order_by(Shipment.updated_at.desc()).limit(25)).all():
            role = "sender" if s.sender_id == uid else "traveller"
            ctx["my_orders"].append({
                "ref": f"S{s.id}", "kind": "parcel (send abroad)", "role": role, "title": s.item_name,
                "route": f"{s.pickup_city} -> {s.destination_city}, {country_name(s.destination_country)}",
                "status": s.status, "status_text": saathi._STATUS_TEXT.get(s.status, s.status),
                "next_action": _NEXT[("shipment", role)].get(s.status), "needed_by": s.needed_by,
                "product_value_inr": _inr(s.declared_value_paise),
                ("you_pay_inr" if role == "sender" else "you_earn_inr"):
                    _inr(s.price_paise if role == "sender" else s.traveller_payout_paise),
                "traveller": s.traveller.name if s.traveller else None, "sender": s.sender.name,
                "travel_date": s.trip.travel_date if s.trip else None, "path": f"/send/{s.id}"})
        for r in db.scalars(select(ProductRequest).where(
                (ProductRequest.buyer_id == uid) | (ProductRequest.traveller_id == uid))
                .order_by(ProductRequest.updated_at.desc()).limit(25)).all():
            role = "buyer" if r.buyer_id == uid else "traveller"
            pending = sum(1 for o in r.offers if o.status == OfferStatus.PENDING)
            ctx["my_orders"].append({
                "ref": f"R{r.id}", "kind": "product request (buy from abroad)", "role": role, "title": r.title,
                "route": f"{country_name(r.source_country)} -> {r.deliver_city}", "status": r.status,
                "status_text": saathi._STATUS_TEXT.get(r.status, r.status),
                "next_action": _NEXT[("request", role)].get(r.status), "needed_by": r.needed_by,
                "pending_offers": pending if role == "buyer" else None,
                ("you_pay_inr" if role == "buyer" else "you_earn_inr"):
                    _inr(r.total_paise if role == "buyer" else r.reward_paise),
                "traveller": r.traveller.name if r.traveller else None, "path": f"/buy/{r.id}"})
        for o in db.scalars(select(Offer).where(Offer.traveller_id == uid, Offer.status == OfferStatus.PENDING)
                            .limit(10)).all():
            ctx["my_orders"].append({
                "ref": f"R{o.request_id}", "kind": "your offer to bring a product", "role": "traveller (offer)",
                "title": o.request.title, "route": f"{country_name(o.request.source_country)} -> "
                                                   f"{o.request.deliver_city}", "status": "offer_pending",
                "status_text": "Your offer is waiting for the buyer to accept.", "next_action": None,
                "you_earn_inr": _inr(o.reward_paise), "path": f"/buy/{o.request_id}"})
        ctx["my_trips"] = [{"route": f"{t.origin_city} -> {t.destination_city}", "travel_date": t.travel_date}
                           for t in db.scalars(select(Trip).where(Trip.traveller_id == uid,
                                                                  Trip.status == TripStatus.ACTIVE).limit(10)).all()]
    parcels = db.scalars(select(Shipment).where(Shipment.status == ShipmentStatus.OPEN, Shipment.sender_id != uid)
                         .order_by(Shipment.created_at.desc()).limit(40)).all()
    reqs = db.scalars(select(ProductRequest).where(ProductRequest.status == RequestStatus.OPEN,
                                                   ProductRequest.buyer_id != uid)
                      .order_by(ProductRequest.created_at.desc()).limit(40)).all()
    ctx["marketplace"] = {
        "open_parcels": [{"ref": f"S{s.id}", "title": s.item_name, "from": s.pickup_city, "to": s.destination_country,
                          "to_city": s.destination_city, "earn_inr": _inr(s.traveller_payout_paise),
                          "needed_by": s.needed_by, "path": f"/send/{s.id}"} for s in parcels],
        "open_buy_requests": [{"ref": f"R{r.id}", "title": r.title, "from": r.source_country,
                               "deliver_city": r.deliver_city, "earn_inr": _inr(r.reward_paise),
                               "needed_by": r.needed_by, "path": f"/buy/{r.id}"} for r in reqs],
    }
    places = {cc for _, cc, _ in saathi.find_places(question)}
    if places:  # keep the prompt focused on the countries the user asked about
        m = ctx["marketplace"]
        m["open_parcels"] = [p for p in m["open_parcels"] if p["to"] in places] or m["open_parcels"][:10]
        m["open_buy_requests"] = [p for p in m["open_buy_requests"] if p["from"] in places] or \
            m["open_buy_requests"][:10]
    return ctx


@router.post("/assistant")
def assistant(body: AssistantIn, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)):
    """Floating Saathi popup: ask anything about your orders, prices or open listings."""
    ctx = _assistant_context(db, user, body.message)
    outcome = saathi.assistant(body.message, [t.model_dump() for t in body.history], ctx)
    paths = {o["ref"]: (o["title"], o["path"]) for o in ctx["my_orders"]}
    for k in ("open_parcels", "open_buy_requests"):
        for m in ctx["marketplace"][k]:
            paths.setdefault(m["ref"], (m["title"], m["path"]))
    links = [{"ref": r, "label": f"{r} · {paths[r][0]}", "path": paths[r][1]}
             for r in outcome.data["order_refs"] if r in paths]
    if user:
        agents.log_run(db, outcome, user.id, ("ESCALATED: " if outcome.data["escalate"] else "Assistant: ")
                       + body.message[:200])
        db.commit()
    return {"reply": outcome.data["reply"], "escalate": outcome.data["escalate"], "links": links,
            "agent": outcome.meta()}

# ------------------------------------------------------------ activity / human review queue

def _run_out(r: AgentRun) -> dict:
    return {"id": r.id, "agent": r.agent, "source": r.source, "status": r.status, "confidence": r.confidence,
            "needs_human": r.needs_human, "resolved": r.resolved, "summary": r.summary, "created_at": r.created_at,
            "entity_type": r.entity_type, "entity_id": r.entity_id}


@router.get("/activity")
def activity(entity_type: str | None = Query(default=None, pattern="^(shipment|request|trip)$"),
             entity_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(AgentRun).order_by(AgentRun.created_at.desc()).limit(50)
    if entity_type and entity_id:
        model = {"shipment": Shipment, "request": ProductRequest, "trip": Trip}[entity_type]
        obj = db.get(model, entity_id)
        parties = {getattr(obj, a, None) for a in ("sender_id", "buyer_id", "traveller_id")} if obj else set()
        if user.id not in parties and not user.is_admin:
            raise HTTPException(404, "Not found")
        q = q.where(AgentRun.entity_type == entity_type, AgentRun.entity_id == entity_id)
    else:
        q = q.where(AgentRun.user_id == user.id)
    return [_run_out(r) for r in db.scalars(q).all()]


@router.get("/review-queue")
def review_queue(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Human-in-the-loop queue: escalations and low-confidence agent decisions (admins only)."""
    if not user.is_admin:
        raise HTTPException(403, "Admins only")
    rows = db.scalars(select(AgentRun).where(AgentRun.needs_human.is_(True), AgentRun.resolved.is_(False))
                      .order_by(AgentRun.created_at.desc()).limit(200)).all()
    return [_run_out(r) for r in rows]


@router.post("/review-queue/{run_id}/resolve")
def resolve(run_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.is_admin:
        raise HTTPException(403, "Admins only")
    run = db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(404, "Not found")
    run.resolved = True
    db.commit()
    return _run_out(run)
