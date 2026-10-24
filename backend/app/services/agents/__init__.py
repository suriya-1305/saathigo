"""Saathi agent layer (Pine Labs AgenticOrg) + persistence helpers."""
from __future__ import annotations

import hashlib
import json

import jwt
from sqlalchemy.orm import Session

from app.core.security import create_token, decode_token
from app.models import AgentRun
from app.services.agents import saathi
from app.services.agents.saathi import Outcome

COMPLIANCE_TOKEN_TYPE = "compliance"

__all__ = ["saathi", "Outcome", "log_run", "shipment_items", "issue_compliance_token", "read_compliance_token"]


def log_run(db: Session, outcome: Outcome, user_id: int | None, summary: str,
            entity_type: str | None = None, entity_id: int | None = None) -> AgentRun:
    run = AgentRun(
        user_id=user_id, agent=outcome.agent, entity_type=entity_type, entity_id=entity_id,
        source=outcome.source, status="needs_human" if outcome.needs_human else "completed",
        confidence=outcome.confidence, needs_human=outcome.needs_human, summary=summary[:500],
        output=json.dumps(outcome.data, default=str, ensure_ascii=False)[:20000],
        run_id=outcome.run_id, latency_ms=outcome.latency_ms,
    )
    db.add(run)
    return run


def shipment_items(item_name: str, description: str | None) -> list[str]:
    """Item lines the compliance agent reviews: the headline plus each bullet/line of the description."""
    lines = [item_name.strip()]
    for line in (description or "").splitlines():
        line = line.strip().lstrip("-*• ").strip()
        if line and line.lower() != lines[0].lower():
            lines.append(line[:200])
    return lines[:20]


def _items_hash(items: list[str], destination_country: str) -> str:
    canon = json.dumps([i.strip().lower() for i in items] + [destination_country.upper()])
    return hashlib.sha256(canon.encode()).hexdigest()


def issue_compliance_token(user_id: int, items: list[str], destination_country: str, outcome: Outcome) -> str:
    """Short-lived signed proof of the compliance verdict, so creating the order needn't re-run the agent."""
    return create_token(user_id, COMPLIANCE_TOKEN_TYPE, expires_minutes=60, extra={
        "h": _items_hash(items, destination_country), "overall": outcome.data["overall"],
        "report": {**outcome.data, "meta": outcome.meta()},
    })


def read_compliance_token(token: str, user_id: int, items: list[str], destination_country: str) -> dict | None:
    try:
        claims = decode_token(token, COMPLIANCE_TOKEN_TYPE)
    except jwt.PyJWTError:
        return None
    if claims.get("sub") != str(user_id) or claims.get("h") != _items_hash(items, destination_country):
        return None
    return claims["report"]
