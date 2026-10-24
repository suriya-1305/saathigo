"""Saathi: the seven AgenticOrg agents wired into the SaathiGo flows.

Every function
  1. hands the agent *platform-verified* data plus a strict JSON contract,
  2. normalises whatever comes back (agents may rename keys or answer in prose), and
  3. falls back to deterministic rules when the agent is disabled, down, or returns nothing usable,
so the marketplace keeps working and humans always have the final say (``needs_human``).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable

from app.data.airports import AIRPORTS, CITY_ALIASES
from app.core.config import settings
from app.data.countries import COUNTRIES, country_name
from app.schemas import SHIPMENT_CATEGORIES
from app.services.agents.client import AgentResult, run_agent

INTENTS = ["send_abroad", "buy_from_abroad", "dabba", "track_order", "traveller", "other"]

PREAMBLE = (
    f"You are part of {settings.app_name}, an Indian peer-to-peer platform: verified air travellers carry parcels from "
    "Indian families to relatives abroad (send) and bring overseas products to buyers in India (buy). "
    "Payments are escrowed via Pine Labs; a human always confirms final decisions. "
)
STRICT = (f" Use ONLY the platform data supplied; it has been verified by {settings.app_name}. "
          "Respond with a single JSON object only, no prose outside JSON.")


@dataclass
class Outcome:
    agent: str
    data: dict
    source: str  # agenticorg | fallback
    confidence: float | None = None
    needs_human: bool = False
    note: str | None = None
    run_id: str | None = None
    latency_ms: int = 0
    extra: dict = field(default_factory=dict)

    def meta(self) -> dict:
        return {"agent": self.agent, "source": self.source, "confidence": self.confidence,
                "needs_human": self.needs_human, "note": self.note, "latency_ms": self.latency_ms}


def _from_agent(res: AgentResult, data: dict, needs_human: bool | None = None) -> Outcome:
    return Outcome(agent=res.agent, data=data, source="agenticorg", confidence=res.confidence,
                   needs_human=res.needs_human if needs_human is None else needs_human,
                   note=res.hitl_reason, run_id=res.run_id, latency_ms=res.latency_ms)


def _fallback(agent: str, data: dict, res: AgentResult | None, needs_human: bool = False) -> Outcome:
    note = "Rule-based fallback" + (f" (agent unavailable: {res.error})" if res and res.error and
                                    res.error != "agents disabled" else "")
    return Outcome(agent=agent, data=data, source="fallback", needs_human=needs_human, note=note,
                   latency_ms=res.latency_ms if res else 0)


def _task(role: str, instructions: str, data: dict | None = None) -> str:
    body = PREAMBLE + f"Your role: {role}. Today is {date.today().isoformat()}. " + instructions + STRICT
    if data is not None:
        body += "\n\nPLATFORM DATA:\n" + json.dumps(data, ensure_ascii=False, default=str)
    return body


# ------------------------------------------------------------------ helpers

_COUNTRY_BY_NAME = {v["name"].lower(): k for k, v in COUNTRIES.items()}
_COUNTRY_BY_NAME.update({"uae": "AE", "usa": "US", "united states of america": "US", "america": "US",
                         "uk": "GB", "england": "GB", "britain": "GB", "u.s.": "US", "u.k.": "GB"})
_CITY_COUNTRY = {city.lower(): cc for city, cc in AIRPORTS.values()}
_CITY_COUNTRY.update({alias.lower(): AIRPORTS[code][1] for alias, code in CITY_ALIASES.items() if code in AIRPORTS})


def resolve_country(value: Any) -> str | None:
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if len(v) == 2 and v.upper() in COUNTRIES:
        return v.upper()
    low = v.lower()
    return _COUNTRY_BY_NAME.get(low) or _CITY_COUNTRY.get(low)


def find_places(text: str) -> list[tuple[str, str, str | None]]:
    """(match, country code, city) for every known country/city mentioned, in order of appearance."""
    low = f" {text.lower()} "
    hits: list[tuple[int, str, str, str | None]] = []
    for name, cc in _COUNTRY_BY_NAME.items():
        i = low.find(f" {name}")
        if i >= 0 and re.match(r"[\s,.!?]", low[i + len(name) + 1: i + len(name) + 2] or " "):
            hits.append((i, name, cc, None))
    for city, cc in _CITY_COUNTRY.items():
        i = low.find(f" {city}")
        if i >= 0 and re.match(r"[\s,.!?]", low[i + len(city) + 1: i + len(city) + 2] or " "):
            hits.append((i, city, cc, city.title()))
    hits.sort()
    return [(m, cc, city) for _, m, cc, city in hits]


def _get(d: dict, *paths: str) -> Any:
    for p in paths:
        cur: Any = d
        for part in p.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
        if cur not in (None, "", []):
            return cur
    return None


_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
                                        "nov", "dec"], 1)}


def parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.strip()[:10]).date()
    except ValueError:
        pass
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3})[a-z]*\.?(?:\s+(\d{4}))?", value.lower())
    if m and m.group(2) in _MONTHS:
        today = date.today()
        year = int(m.group(3)) if m.group(3) else today.year
        try:
            d = date(year, _MONTHS[m.group(2)], int(m.group(1)))
        except ValueError:
            return None
        return d if m.group(3) or d >= today else d.replace(year=year + 1)
    return None


def _num(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, dict):
        return _num(value.get("value"))
    if isinstance(value, str):
        m = re.search(r"\d+(?:\.\d+)?", value.replace(",", ""))
        return float(m.group(0)) if m else None
    return None


def _items(raw: Any) -> list[dict]:
    out = []
    for it in raw if isinstance(raw, list) else []:
        if isinstance(it, str):
            it = {"name": it}
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or it.get("item") or "").strip()
        if not name:
            continue
        out.append({
            "name": name[:120],
            "quantity": max(1, int(_num(it.get("quantity")) or 1)),
            "unit": str(it.get("unit") or "piece")[:20],
            "approx_weight_kg": _num(it.get("approx_weight_kg") or it.get("weight_kg")),
            "approx_value_inr": int(_num(it.get("approx_value_inr") or it.get("value_inr")) or 0) or None,
        })
    return out[:20]


def _transcript(message: str, history: list[dict]) -> list[dict]:
    turns = [{"role": h.get("role", "user"), "content": str(h.get("content", ""))[:1500]} for h in history[-10:]]
    return turns + [{"role": "user", "content": message[:2000]}]


# ------------------------------------------------------------------ concierge

def _guess_intent(text: str) -> str:
    t = text.lower()
    if re.search(r"\b(dabba|hamper|gift box|box of)\b", t):
        return "dabba"
    if re.search(r"\b(where is|track|status|delayed|not (yet )?(arrived|received)|otp|refund|damaged)\b", t):
        return "track_order"
    if re.search(r"\b(i'?m (flying|travell?ing)|my trip|boarding pass|carry for|earn)\b", t):
        return "traveller"
    if re.search(r"https?://|\b(buy|bring|get me|order from|purchase|amazon|costco|from (the )?(us|uk|dubai))\b", t):
        return "buy_from_abroad"
    if re.search(r"\b(send|bhej|courier|parcel|to my (son|daughter|brother|sister|mother|father|family))\b", t):
        return "send_abroad"
    return "other"


_CONCIERGE_REPLIES = {
    "send_abroad": "Happy to help you send this abroad! I've drafted the order below - please check the details.",
    "buy_from_abroad": "Sure! I've drafted a buy request below. A verified traveller from that country can bring it.",
    "dabba": "Lovely idea - pick one of our ready-made dabbas and I'll curate it for the destination.",
    "track_order": "Let me help with your order. Open it from your dashboard and ask me there - I'll check its timeline.",
    "traveller": "Travelling soon? Scan your boarding pass to verify the trip and see orders on your route.",
    "other": "I can help you send things to family abroad, buy products from overseas, or earn while travelling. "
             "What would you like to do?",
}


def concierge(message: str, history: list[dict]) -> Outcome:
    convo = _transcript(message, history)
    res = run_agent("concierge", _task(
        "Saathi Concierge - the friendly front door",
        "Read the conversation, reply warmly and briefly to the user (max 3 sentences, simple English), "
        f"classify intent as one of {INTENTS}, and name the next agent. Return JSON "
        '{"reply": str, "intent": str, "route_to": "intake|dabba_curator|tracking_support|none", '
        '"missing_info": [str]}.', {"conversation": convo}))
    intent = str(res.output.get("intent") or "").strip().lower() if res.ok else ""
    reply = res.output.get("reply") or res.text if res.ok else None
    if intent not in INTENTS:
        intent = _guess_intent(" ".join(t["content"] for t in convo if t["role"] == "user"))
    if res.ok and reply:
        return _from_agent(res, {"reply": str(reply), "intent": intent,
                                 "missing_info": res.output.get("missing_info") or []})
    return _fallback("concierge", {"reply": _CONCIERGE_REPLIES[intent], "intent": intent, "missing_info": []}, res)


# ------------------------------------------------------------------ intake

_COUNT_UNITS = {"", "item", "items", "piece", "pieces", "pc", "pcs", "nos", "no", "unit", "units", "count"}


def _item_line(i: dict) -> str:
    unit = str(i.get("unit") or "").strip()
    qty = i["quantity"]
    qty = int(qty) if float(qty).is_integer() else qty
    return f"- {qty} {i['name']}" if unit.lower() in _COUNT_UNITS else f"- {qty} {unit} {i['name']}"


def normalize_send_draft(raw: dict, fallback_text: str = "") -> dict:
    items = _items(raw.get("items"))
    dest_cc = resolve_country(_get(raw, "destination_country", "destination.country", "destination.country_code"))
    dest_city = _get(raw, "destination_city", "destination.city")
    if not dest_cc and dest_city:
        dest_cc = resolve_country(dest_city)
    if dest_cc == "IN":
        dest_cc = None
    weight = _num(_get(raw, "weight_kg", "total_weight_kg", "weight"))
    if not weight and items and all(i["approx_weight_kg"] for i in items):
        weight = sum(i["approx_weight_kg"] * i["quantity"] for i in items)
    category = str(raw.get("category") or "").lower()
    if category not in SHIPMENT_CATEGORIES:
        category = _guess_category(" ".join(i["name"] for i in items) or fallback_text)
    item_name = str(raw.get("item_name") or "").strip() or ", ".join(
        f"{i['quantity']} {i['name']}" if i["quantity"] > 1 else i["name"] for i in items)[:200]
    value = _num(_get(raw, "declared_value_inr", "estimated_value", "value_inr"))
    if not value and items and all(i["approx_value_inr"] for i in items):
        value = sum(i["approx_value_inr"] * i["quantity"] for i in items)
    draft = {
        "kind": "send", "items": items, "item_name": item_name or fallback_text[:60],
        "description": "\n".join(_item_line(i) for i in items) or None,
        "category": category,
        "pickup_city": _get(raw, "pickup_city", "origin.city", "origin_city"),
        "destination_country": dest_cc, "destination_city": dest_city,
        "needed_by": (parse_date(_get(raw, "needed_by", "need_by_date", "deadline")) or None),
        "weight_kg": round(min(weight, 23), 2) if weight else None,
        "declared_value_inr": int(value) if value else None,
        "recipient_name": _get(raw, "recipient_name", "recipient.name"),
    }
    required = ["item_name", "pickup_city", "destination_country", "destination_city", "declared_value_inr"]
    draft["missing_fields"] = [k for k in required if not draft.get(k)]
    return draft


def normalize_buy_draft(raw: dict, fallback_text: str = "") -> dict:
    src = resolve_country(_get(raw, "source_country", "origin.country", "origin_country", "from_country"))
    if src == "IN":
        src = None
    url = _get(raw, "product_url", "url", "link")
    if not url:
        m = re.search(r"https?://\S+", fallback_text)
        url = m.group(0) if m else None
    draft = {
        "kind": "buy", "product_url": url,
        "title": str(_get(raw, "title", "product", "item_name") or "")[:300] or None,
        "quantity": int(_num(raw.get("quantity")) or 1),
        "source_country": src,
        "deliver_city": _get(raw, "deliver_city", "destination.city", "destination_city"),
        "needed_by": parse_date(_get(raw, "needed_by", "need_by_date", "deadline")),
        "price_amount": _num(_get(raw, "price_amount", "price", "estimated_value")),
        "price_currency": str(_get(raw, "price_currency", "currency", "buyer_currency") or "")[:3].upper() or None,
    }
    if not draft["title"] and isinstance(raw.get("items"), list) and raw["items"]:
        draft["title"] = _items(raw["items"])[0]["name"] if _items(raw["items"]) else None
    draft["missing_fields"] = [k for k in ("product_url", "title", "source_country", "deliver_city") if not draft[k]]
    return draft


def _guess_category(text: str) -> str:
    t = text.lower()
    rules = [("documents", r"document|paper|certificate|passport|letter"),
             ("medicines_prescribed", r"medicine|tablet|prescription|syrup"),
             ("clothing", r"kurta|saree|sari|shirt|dress|cloth|lehenga|dupatta|shawl|jacket"),
             ("food_sealed", r"sweet|mithai|laddoo|ladoo|pickle|achar|masala|snack|namkeen|tea|food|spice|katli"),
             ("books", r"book|novel"),
             ("electronics_small", r"phone|charger|earbud|headphone|watch|camera|laptop|kindle"),
             ("gifts", r"gift|rakhi|toy|diya|decor")]
    for cat, pat in rules:
        if re.search(pat, t):
            return cat
    return "other"


def _fallback_intake(text: str, intent: str) -> dict:
    places = find_places(text)
    foreign = [p for p in places if p[1] != "IN"]
    indian = [p for p in places if p[1] == "IN" and p[2]]
    weight = re.search(r"(\d+(?:\.\d+)?)\s*(kg|kgs|kilo)", text.lower())
    value = re.search(r"(?:rs\.?|inr|₹|worth|value(?:d)?(?: at)?)\s*(?:rs\.?|inr|₹)?\s*([\d,]{3,})", text.lower())
    date_m = re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}(?:\s+\d{4})?", text)
    if intent == "buy_from_abroad":
        return normalize_buy_draft({
            "source_country": foreign[0][1] if foreign else None,
            "deliver_city": indian[0][2] if indian else None,
            "needed_by": date_m.group(0) if date_m else None,
        }, text)
    return normalize_send_draft({
        "item_name": re.sub(r"\s+", " ", text)[:80],
        "pickup_city": indian[0][2] if indian else None,
        "destination_country": foreign[0][1] if foreign else None,
        "destination_city": next((p[2] for p in foreign if p[2]), None),
        "needed_by": date_m.group(0) if date_m else None,
        "weight_kg": float(weight.group(1)) if weight else None,
        "declared_value_inr": int(value.group(1).replace(",", "")) if value else None,
    }, text)


def intake(message: str, history: list[dict], intent: str) -> Outcome:
    convo = _transcript(message, history)
    kind = "buy" if intent == "buy_from_abroad" else "send"
    schema = (
        '{"kind":"send","items":[{"name":str,"quantity":int,"unit":str,"approx_weight_kg":float|null,'
        '"approx_value_inr":int|null}],"item_name":str,"category":one of ' + json.dumps(SHIPMENT_CATEGORIES) +
        ',"pickup_city":str|null (city in India),"destination_country":"ISO-3166 alpha-2"|null,'
        '"destination_city":str|null,"needed_by":"YYYY-MM-DD"|null,"weight_kg":float|null,'
        '"declared_value_inr":int|null,"recipient_name":str|null,"missing_fields":[str]}'
        if kind == "send" else
        '{"kind":"buy","product_url":str|null,"title":str|null,"quantity":int,'
        '"source_country":"ISO-3166 alpha-2 country the product is bought in"|null,"deliver_city":str|null '
        '(city in India),"needed_by":"YYYY-MM-DD"|null,"price_amount":float|null,"price_currency":str|null,'
        '"missing_fields":[str]}')
    res = run_agent("intake", _task(
        "Saathi Intake - turn the family's message into a clear order",
        f"Extract a {kind} order from the whole conversation. Do not invent values; use null when unknown. "
        f"Return JSON {schema}.", {"conversation": convo}))
    text = " ".join(t["content"] for t in convo if t["role"] == "user")
    if res.ok and res.output:
        norm = normalize_buy_draft if kind == "buy" else normalize_send_draft
        draft = norm(res.output, text)
        # fill gaps the model left with deterministic extraction
        for k, v in _fallback_intake(text, intent).items():
            if k != "missing_fields" and not draft.get(k) and v:
                draft[k] = v
        draft["missing_fields"] = [f for f in draft["missing_fields"] if not draft.get(f)]
        return _from_agent(res, draft)
    return _fallback("intake", _fallback_intake(text, intent), res)


# ------------------------------------------------------------------ dabba curator

def curate_dabba(dabba: dict, country: str, needed_by: date | None, preferences: str | None) -> Outcome:
    route = f"India -> {country_name(country)}" if dabba["kind"] == "swadeshi" else f"{country_name(country)} -> India"
    data = {"dabba": dabba["name"], "route": route, "needed_by": needed_by, "preferences": preferences or "",
            "max_weight_kg": dabba["max_weight_kg"], "candidate_items": dabba["candidates"]}
    res = run_agent("dabba_curator", _task(
        "Saathi Dabba Curator - list everything inside a ready-made box",
        "Choose items ONLY from candidate_items (exact names) to build a balanced box within max_weight_kg, "
        "respecting preferences. Return JSON {\"items\":[{\"name\":str,\"quantity\":int}],\"notes\":str}.", data))
    by_name = {c["name"].lower(): c for c in dabba["candidates"]}

    def build(picks: list[tuple[str, int]]) -> list[dict]:
        out, weight = [], 0.0
        for name, qty in picks:
            c = by_name.get(name.lower()) or next((v for k, v in by_name.items() if name.lower() in k or k in
                                                    name.lower()), None)
            if not c or any(o["name"] == c["name"] for o in out):
                continue
            qty = max(1, min(int(qty or 1), 5))
            while qty and weight + c["approx_weight_kg"] * qty > dabba["max_weight_kg"]:
                qty -= 1
            if qty:
                weight += c["approx_weight_kg"] * qty
                out.append({**c, "quantity": qty})
        return out

    items = build([(i["name"], i["quantity"]) for i in _items(res.output.get("items"))]) if res.ok else []
    if items:
        notes = str(res.output.get("notes") or "")
        return _from_agent(res, _dabba_summary(dabba, items, notes))
    items = build([(c["name"], 1) for c in dabba["candidates"]])
    return _fallback("dabba_curator", _dabba_summary(dabba, items, "Standard box contents."), res)


def _dabba_summary(dabba: dict, items: list[dict], notes: str) -> dict:
    return {"dabba_id": dabba["id"], "name": dabba["name"], "kind": dabba["kind"], "category": dabba["category"],
            "items": items, "notes": notes,
            "total_weight_kg": round(sum(i["approx_weight_kg"] * i["quantity"] for i in items), 2),
            "total_value_inr": sum(i["approx_value_inr"] * i["quantity"] for i in items)}


# ------------------------------------------------------------------ compliance

_NOT_ALLOWED = r"e-?cig|vape|cannabis|marijuana|ganja|narcotic|drug|weapon|gun|knife|ammunition|explosive|" \
               r"firework|cracker|lighter|gold|silver bar|currency|cash|counterfeit|ivory|live animal|aerosol|" \
               r"lithium batter(y|ies) spare|power ?bank|poppy|khat|betel|gutkha|meat|raw fish"
_NEEDS_CHECK = r"food|sweet|mithai|laddoo|ladoo|pickle|achar|masala|spice|powder|ghee|honey|seed|plant|tea|" \
               r"namkeen|snack|dry ?fruit|medicine|tablet|syrup|ayurved|perfume|liquid|oil|cream|cosmetic|" \
               r"battery|electronic|phone|homemade|katli|chocolate|dates"


def _fallback_verdict(item: str) -> dict:
    t = item.lower()
    if re.search(_NOT_ALLOWED, t):
        return {"item": item, "status": "not_allowed", "reason": "Commonly prohibited or restricted for "
                "carriage by passengers or at customs.", "packing_note": "Remove this item."}
    if re.search(_NEEDS_CHECK, t):
        return {"item": item, "status": "needs_label_check", "reason": "Food, medicine, liquids and batteries "
                "need labels and destination rules checked.", "packing_note": "Use sealed retail packaging with "
                "ingredient/content labels; keep bills for declaration."}
    return {"item": item, "status": "clear", "reason": "No common restriction found for this kind of item.",
            "packing_note": "Pack securely; keep proof of value."}


_STATUS_MAP = {"clear": "clear", "allowed": "clear", "ok": "clear", "permitted": "clear",
               "needs_label_check": "needs_label_check", "needs_review": "needs_label_check",
               "review": "needs_label_check", "restricted": "needs_label_check",
               "not_allowed": "not_allowed", "prohibited": "not_allowed", "blocked": "not_allowed",
               "banned": "not_allowed"}


def compliance_overall(items: list[dict]) -> str:
    statuses = {i["status"] for i in items}
    return "blocked" if "not_allowed" in statuses else "needs_review" if "needs_label_check" in statuses else "clear"


def check_compliance(items: list[str], origin_country: str, destination_country: str) -> Outcome:
    items = [i.strip()[:200] for i in items if i and i.strip()][:20]
    route = f"{country_name(origin_country)} -> {country_name(destination_country)}"
    res = run_agent("compliance", _task(
        "Saathi Compliance - check every item against customs and airline rules for the route",
        "For each item return status clear | needs_label_check | not_allowed. When unsure, use "
        "needs_label_check. Return JSON {\"items\":[{\"item\":str,\"status\":str,\"reason\":str,"
        "\"packing_note\":str}],\"guidance\":str,\"next_step\":str}.", {"route": route, "items": items}))
    verdicts: list[dict] = []
    if res.ok and isinstance(res.output.get("items"), list):
        got = [v for v in res.output["items"] if isinstance(v, dict)]
        for idx, name in enumerate(items):
            match = next((v for v in got if str(v.get("item", "")).lower().strip() == name.lower()), None) or \
                (got[idx] if idx < len(got) else None)
            if not match:
                verdicts.append({"item": name, "status": "needs_label_check",
                                 "reason": "Not reviewed by the compliance agent.", "packing_note": ""})
                continue
            status = _STATUS_MAP.get(str(match.get("status", "")).lower().replace(" ", "_"), "needs_label_check")
            # a hard rule match always wins over a model "clear"
            if status == "clear" and _fallback_verdict(name)["status"] == "not_allowed":
                status = "needs_label_check"
            verdicts.append({"item": name, "status": status, "reason": str(match.get("reason") or "")[:500],
                             "packing_note": str(match.get("packing_note") or "")[:500]})
        overall = compliance_overall(verdicts)
        return _from_agent(res, {"route": route, "items": verdicts, "overall": overall,
                                 "guidance": str(res.output.get("guidance") or "")[:600],
                                 "next_step": str(res.output.get("next_step") or "")[:600]},
                           needs_human=res.needs_human or overall != "clear")
    verdicts = [_fallback_verdict(i) for i in items]
    overall = compliance_overall(verdicts)
    return _fallback("compliance", {
        "route": route, "items": verdicts, "overall": overall,
        "guidance": "Guidance based on common rules, not legal advice. The traveller declares items at customs.",
        "next_step": "Fix or remove flagged items, then confirm." if overall != "clear" else "Ready for matching.",
    }, res, needs_human=overall != "clear")


# ------------------------------------------------------------------ matching

def rank_candidates(purpose: str, subject: dict, candidates: list[dict],
                    score: Callable[[dict], tuple[int, str]]) -> Outcome:
    """Rank pre-filtered, eligible candidates (each has an ``id``). ``score`` is the deterministic fallback."""
    if not candidates:
        return Outcome(agent="matching", data={"ranked": [], "excluded": []}, source="fallback",
                       note="No eligible candidates")
    res = run_agent("matching", _task(
        "Saathi Matching - rank who should take this order",
        f"{purpose} All candidates are already eligible on route and capacity. Rank by date fit before "
        "needed_by, spare capacity, reliability and verification. Return JSON {\"ranked\":[{\"id\":int,"
        "\"score\":0-100,\"reason\":str}],\"excluded\":[{\"id\":int,\"reason\":str}]}.",
        {"order": subject, "candidates": candidates}))
    ids = {c["id"] for c in candidates}
    if res.ok and isinstance(res.output.get("ranked"), list):
        ranked, seen = [], set()
        for r in res.output["ranked"]:
            cid = r.get("id", r.get("trip_id")) if isinstance(r, dict) else None
            if cid in ids and cid not in seen:
                seen.add(cid)
                ranked.append({"id": cid, "score": max(0, min(100, int(_num(r.get("score")) or 50))),
                               "reason": str(r.get("reason") or "")[:300]})
        excluded = [{"id": e.get("id", e.get("trip_id")), "reason": str(e.get("reason") or "")[:300]}
                    for e in res.output.get("excluded") or [] if isinstance(e, dict)
                    and e.get("id", e.get("trip_id")) in ids and e.get("id", e.get("trip_id")) not in seen]
        excluded = list({e["id"]: e for e in excluded}.values())
        seen |= {e["id"] for e in excluded}
        for c in candidates:  # never silently drop an eligible candidate
            if c["id"] not in seen:
                s, why = score(c)
                ranked.append({"id": c["id"], "score": s, "reason": why})
        # Platform filters already made these eligible: keep agent exclusions visible (last) for a human to judge.
        ranked += [{"id": e["id"], "score": min(20, score(next(c for c in candidates if c["id"] == e["id"]))[0]),
                    "reason": f"Saathi flagged: {e['reason'] or 'not recommended'}", "flagged": True}
                   for e in excluded]
        if ranked:
            return _from_agent(res, {"ranked": ranked, "excluded": excluded},
                               needs_human=res.needs_human or bool(excluded))
    ranked = sorted(({"id": c["id"], "score": s, "reason": why} for c in candidates for s, why in [score(c)]),
                    key=lambda r: -r["score"])
    return _fallback("matching", {"ranked": ranked, "excluded": []}, res)


def date_fit_score(travel_or_due: date | None, needed_by: date | None, base: int = 60) -> tuple[int, str]:
    if not needed_by or not travel_or_due:
        return base, "No deadline set"
    slack = (needed_by - travel_or_due).days
    if slack < 0:
        return 10, "Arrives after the needed-by date"
    return min(100, base + 25 - min(slack, 25)), f"Arrives {slack} day(s) before the deadline"


# ------------------------------------------------------------------ negotiation

def suggest_reward(context: dict, offers: list[dict] | None = None) -> Outcome:
    offers = offers or []
    fb = _fallback_reward(context, offers)
    pricing = {"policy": "Traveller reward is ~10% of item value (min Rs 500, max Rs 8,000), +15% when the "
                         "deadline is within 7 days. Fair range is 0.8x-1.25x of the baseline.",
               "baseline_reward_inr": fb["suggested_reward_inr"], "fair_min_inr": fb["min_inr"],
               "fair_max_inr": fb["max_inr"]}
    res = run_agent("negotiation", _task(
        "Saathi Negotiation - suggest a fair traveller reward; a person always accepts the final price",
        "platform_pricing is the output of the platform's pricing function. Starting from its baseline, suggest a fair "
        "reward in INR (you may adjust within the fair range for urgency/item size), and assess each existing "
        "offer as fair, high or low. Return JSON {\"suggested_reward_inr\":int,\"min_inr\":int,\"max_inr\":int,"
        "\"rationale\":str,\"message\":str,\"offer_assessments\":[{\"offer_id\":int,\"verdict\":\"fair|high|low\","
        "\"note\":str}]}.",
        {**context, "platform_pricing": pricing, "offers": offers}))
    if res.ok and _num(res.output.get("suggested_reward_inr")):
        s = int(_num(res.output["suggested_reward_inr"]))
        lo = int(_num(res.output.get("min_inr")) or s * 0.8)
        hi = int(_num(res.output.get("max_inr")) or s * 1.25)
        lo, hi = min(lo, s), max(hi, s)
        assessments = {a.get("offer_id"): a for a in res.output.get("offer_assessments") or [] if isinstance(a, dict)}
        out_assess = []
        for o in offers:
            a = assessments.get(o["offer_id"])
            verdict = str(a.get("verdict", "")).lower() if a else ""
            out_assess.append({"offer_id": o["offer_id"], "verdict": verdict if verdict in {"fair", "high", "low"}
                               else _verdict(o["reward_inr"], lo, hi), "note": str(a.get("note") or "") if a else ""})
        return _from_agent(res, {"suggested_reward_inr": max(100, s), "min_inr": max(100, lo), "max_inr": hi,
                                 "rationale": str(res.output.get("rationale") or "")[:600],
                                 "message": str(res.output.get("message") or res.output.get("message_to_sender")
                                                or "")[:600], "offer_assessments": out_assess})
    return _fallback("negotiation", fb, res)


def _verdict(amount: int, lo: int, hi: int) -> str:
    return "high" if amount > hi else "low" if amount < lo else "fair"


def _fallback_reward(ctx: dict, offers: list[dict]) -> dict:
    value = float(ctx.get("item_value_inr") or ctx.get("courier_estimate_inr") or 5000)
    s = max(500, min(8000, round(value * 0.10 / 50) * 50))
    nb = parse_date(str(ctx.get("needed_by") or ""))
    if nb and (nb - date.today()) <= timedelta(days=7):
        s = round(s * 1.15 / 50) * 50
    lo, hi = int(s * 0.8), int(s * 1.25)
    return {"suggested_reward_inr": int(s), "min_inr": lo, "max_inr": hi,
            "rationale": "About 10% of item value (min Rs 500, max Rs 8,000), +15% for deadlines within a week.",
            "message": f"A reward around Rs {int(s):,} is fair for this order.",
            "offer_assessments": [{"offer_id": o["offer_id"], "verdict": _verdict(o["reward_inr"], lo, hi),
                                   "note": ""} for o in offers]}


# ------------------------------------------------------------------ tracking & support

_ESCALATE = r"damag|broken|lost|missing|stolen|fraud|scam|refund|police|complain|wrong item|never received|cheat"


def support(question: str, order: dict, history: list[dict]) -> Outcome:
    res = run_agent("tracking_support", _task(
        "Saathi Tracking & Support - follow the order from pickup to delivery and help the user",
        "Answer the user's question using the order timeline. Never invent locations or dates. Escalate to a "
        "human for disputes, damage, loss, refunds or anything you cannot resolve. Return JSON "
        "{\"reply\":str,\"escalate_to_human\":bool,\"next_steps\":[str]}.",
        {"question": question[:1000], "conversation": history[-6:], "order": order}))
    hard_escalate = bool(re.search(_ESCALATE, question.lower()))
    if res.ok and (res.output.get("reply") or res.text):
        esc = bool(res.output.get("escalate_to_human")) or hard_escalate
        steps = [str(s)[:300] for s in res.output.get("next_steps") or [] if s][:5]
        return _from_agent(res, {"reply": str(res.output.get("reply") or res.text)[:1500], "escalate": esc,
                                 "next_steps": steps}, needs_human=esc)
    return _fallback("tracking_support", _fallback_support(order, hard_escalate), res, needs_human=hard_escalate)


_STATUS_TEXT = {
    "open": "Your order is live and waiting for a verified traveller on this route.",
    "accepted": "A traveller's offer was accepted - complete the payment to lock it in.",
    "matched": "A verified traveller has accepted - complete the payment to lock it in.",
    "paid": "Payment is safely held in escrow. The traveller will collect / buy the item next.",
    "purchased": "The traveller has bought your item (photo proof is on the order) and will bring it on their flight.",
    "in_transit": "The traveller has your item (handover photo captured) and is carrying it on their flight.",
    "delivered": "This order is delivered and the traveller has been paid.",
    "cancelled": "This order was cancelled.",
}


def _fallback_support(order: dict, escalate: bool) -> dict:
    reply = _STATUS_TEXT.get(order.get("status", ""), "I can see your order.")
    if order.get("traveller_flight"):
        reply += f" Traveller's flight: {order['traveller_flight']}."
    if escalate:
        reply += " I've flagged this to our support team - a person will contact you shortly."
    return {"reply": reply, "escalate": escalate,
            "next_steps": ["Share the delivery OTP only when you have the item in hand."]}

# ------------------------------------------------------------------ order assistant (popup)

_ORDER_REF = re.compile(r"\b([SR])\s*-?\s*#?\s*(\d{1,6})\b", re.I)
_PRICING_Q = r"fee|price|pricing|cost|charge|commission|earn|reward|how much|percent|%"


def _mentioned_orders(question: str, orders: list[dict]) -> list[dict]:
    q = question.lower()
    refs = {f"{k.upper()}{n}" for k, n in _ORDER_REF.findall(question)}
    hits = [o for o in orders if o["ref"] in refs]
    if not hits:
        words = {w for w in re.findall(r"[a-z]{4,}", q)} - {"order", "where", "status", "what", "when", "parcel",
                                                           "request", "about", "with", "have", "will"}
        hits = [o for o in orders if words & set(re.findall(r"[a-z]{4,}", o["title"].lower()))]
    return hits[:5]


def _fallback_assistant(question: str, ctx: dict) -> dict:
    q = question.lower()
    orders = ctx.get("my_orders") or []
    found = _mentioned_orders(question, orders)
    parts: list[str] = []
    if re.search(_PRICING_Q, q):
        p = ctx["pricing"]
        parts.append(f"Pricing is based on the product value: the traveller earns {p['traveller_reward_pct']}% and "
                     f"{p['platform']} keeps {p['platform_fee_pct']}%. So for a Rs 10,000 item the traveller earns "
                     f"Rs {100 * p['traveller_reward_pct']:.0f} and the fee is Rs {100 * p['platform_fee_pct']:.0f}.")
    if found:
        for o in found:
            parts.append(f"{o['ref']} \"{o['title']}\" ({o['route']}): {o['status_text']}"
                         + (f" Next: {o['next_action']}" if o.get("next_action") else ""))
    places = [cc for _, cc, _ in find_places(question) if cc != "IN"]
    if places and not found:
        cc = places[0]
        market = ctx.get("marketplace") or {}
        parcels = [m for m in market.get("open_parcels", []) if m["to"] == cc]
        reqs = [m for m in market.get("open_buy_requests", []) if m["from"] == cc]
        msg = f"For {country_name(cc)}: {len(parcels)} parcel(s) waiting for a traveller from India"
        if parcels:
            msg += " - " + "; ".join(f"{m['ref']} {m['title']} (earn Rs {m['earn_inr']})" for m in parcels[:4])
        msg += f". {len(reqs)} product request(s) to bring back to India"
        if reqs:
            msg += " - " + "; ".join(f"{m['ref']} {m['title']} (earn Rs {m['earn_inr']})" for m in reqs[:4])
        parts.append(msg + ".")
    if not parts:
        active = [o for o in orders if o["status"] not in ("delivered", "cancelled")]
        if not ctx.get("signed_in"):
            parts.append("Log in and I can tell you the status of your parcels and requests. You can also browse "
                         "Send abroad / Buy from abroad to see what people need carried.")
        elif active:
            parts.append(f"You have {len(active)} active order(s): " + "; ".join(
                f"{o['ref']} {o['title']} - {o['status_text']}" for o in active[:5]))
        else:
            parts.append("You have no active orders yet. Post a parcel under Send abroad or a product under Buy "
                         "from abroad, or open either list to pick something up on your next trip.")
    escalate = bool(re.search(_ESCALATE, q))
    if escalate:
        parts.append("I've flagged this to our support team - a person will contact you shortly.")
    return {"reply": " ".join(parts), "order_refs": [o["ref"] for o in found], "escalate": escalate}


def assistant(question: str, history: list[dict], ctx: dict) -> Outcome:
    """Answers any question about the user's orders, prices or open listings using platform data only."""
    res = run_agent("tracking_support", _task(
        "Saathi Assistant - answer the user's questions about their orders, prices and open listings",
        "Use my_orders (the signed-in user's parcels, product requests, offers and trips with live status), "
        "marketplace (open parcels and buy requests other users posted) and pricing. Refer to orders by their "
        "ref (e.g. S3, R2). Be short and specific. Never invent orders, dates or amounts; if something is not in "
        "the data say so. Escalate disputes, damage, loss or refunds to a human. Return JSON "
        "{\"reply\":str,\"order_refs\":[str],\"escalate_to_human\":bool}.",
        {"question": question[:1000], "conversation": history[-6:], **ctx}))
    known = {o["ref"] for o in ctx.get("my_orders") or []} | {
        m["ref"] for k in ("open_parcels", "open_buy_requests") for m in (ctx.get("marketplace") or {}).get(k, [])}
    hard_escalate = bool(re.search(_ESCALATE, question.lower()))
    reply = res.output.get("reply") if res.ok else None
    if res.ok and (reply or res.text):
        refs = [str(r).upper().replace(" ", "") for r in res.output.get("order_refs") or []]
        refs = [r for r in refs if r in known] or [o["ref"] for o in _mentioned_orders(question, ctx["my_orders"])]
        esc = bool(res.output.get("escalate_to_human")) or hard_escalate
        return _from_agent(res, {"reply": str(reply or res.text)[:1500], "order_refs": refs[:5], "escalate": esc},
                           needs_human=esc)
    return _fallback("tracking_support", _fallback_assistant(question, ctx), res, needs_human=hard_escalate)
