"""Thin client for Pine Labs AgenticOrg: POST /api/v1/agents/{id}/run.

Agents answer with either a structured JSON ``output`` or ``{"raw_output": "<text>"}``. Most runs come back
with status ``hitl_triggered`` (confidence under the tenant's floor) - that is a *successful* run which simply
asks for a human to confirm, so we surface it as ``needs_human`` instead of treating it as an error.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)

AGENTS = {
    "concierge": "agent_concierge_id",
    "intake": "agent_intake_id",
    "dabba_curator": "agent_dabba_curator_id",
    "compliance": "agent_compliance_id",
    "matching": "agent_matching_id",
    "negotiation": "agent_negotiation_id",
    "tracking_support": "agent_tracking_support_id",
}


@dataclass
class AgentResult:
    agent: str
    ok: bool
    output: dict = field(default_factory=dict)
    text: str | None = None
    status: str = "error"
    confidence: float | None = None
    needs_human: bool = False
    hitl_reason: str | None = None
    run_id: str | None = None
    latency_ms: int = 0
    error: str | None = None


_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


def parse_output(raw: Any) -> tuple[dict, str | None]:
    """Return (structured dict, free text). Pulls JSON out of raw text answers when present."""
    if isinstance(raw, dict) and set(raw) - {"raw_output", "status"}:
        return raw, None
    text = raw.get("raw_output") if isinstance(raw, dict) else raw if isinstance(raw, str) else None
    if not text:
        return {}, None
    m = _JSON_BLOCK.search(text)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict):
                return data, None
        except ValueError:
            pass
    return {}, text.strip()


def run_agent(agent: str, task: str, data: dict | None = None) -> AgentResult:
    if not settings.agents_enabled:
        return AgentResult(agent=agent, ok=False, error="agents disabled")
    agent_id = getattr(settings, AGENTS[agent])
    payload = {"action": "process", "inputs": {"task": task, "data": data or {}}, "context": data or {}}
    started = time.monotonic()
    try:
        r = httpx.post(
            f"{settings.agenticorg_base_url.rstrip('/')}/api/v1/agents/{agent_id}/run",
            headers={"Authorization": f"Bearer {settings.agenticorg_api_key}"},
            json=payload, timeout=settings.agenticorg_timeout_s,
        )
        latency = int((time.monotonic() - started) * 1000)
        r.raise_for_status()
        body = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("AgenticOrg %s failed: %s", agent, exc)
        return AgentResult(agent=agent, ok=False, error=str(exc)[:300],
                           latency_ms=int((time.monotonic() - started) * 1000))

    status = str(body.get("status") or "unknown")
    if body.get("error") or status in {"failed", "error"}:
        return AgentResult(agent=agent, ok=False, status=status, error=str(body.get("error"))[:300],
                           run_id=body.get("run_id"), latency_ms=latency)
    output, text = parse_output(body.get("output"))
    return AgentResult(
        agent=agent, ok=bool(output or text), output=output, text=text, status=status,
        confidence=body.get("confidence"), needs_human=status == "hitl_triggered",
        hitl_reason=body.get("hitl_trigger"), run_id=body.get("run_id"), latency_ms=latency,
    )
