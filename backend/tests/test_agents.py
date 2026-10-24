from datetime import date, timedelta

import httpx

from app.core.config import settings
from app.services.agents import client as agent_client
from app.services.agents import saathi

SHIP = {"pickup_city": "Pune", "destination_country": "AE", "destination_city": "Dubai",
        "item_name": "Silk saree", "declared_value_inr": 5000}


def test_parse_output_variants():
    assert agent_client.parse_output({"reply": "hi"}) == ({"reply": "hi"}, None)
    assert agent_client.parse_output({"raw_output": 'Sure: {"a": 1}', "status": "completed"}) == ({"a": 1}, None)
    assert agent_client.parse_output({"raw_output": "Please share the date."}) == ({}, "Please share the date.")


def test_agenticorg_compliance_is_normalised(monkeypatch):
    monkeypatch.setattr(settings, "agent_provider", "agenticorg")
    monkeypatch.setattr(settings, "agenticorg_api_key", "ao_sk_test")
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen["url"], seen["auth"] = url, headers["Authorization"]
        body = {"status": "hitl_triggered", "confidence": 0.9, "run_id": "msg_1", "hitl_trigger": "confidence < 0.95",
                "output": {"items": [{"item": "Silk saree", "status": "Clear", "reason": "clothing"},
                                     {"item": "Vape pen", "status": "clear", "reason": "?"}]}}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(agent_client.httpx, "post", fake_post)
    out = saathi.check_compliance(["Silk saree", "Vape pen", "Mango pickle"], "IN", "AE")
    assert seen["url"].endswith(f"/api/v1/agents/{settings.agent_compliance_id}/run")
    assert seen["auth"] == "Bearer ao_sk_test"
    assert out.source == "agenticorg" and out.needs_human
    statuses = [i["status"] for i in out.data["items"]]
    # model said "clear" for a vape -> hard rule downgrades; unreviewed item -> needs check
    assert statuses == ["clear", "needs_label_check", "needs_label_check"]
    assert out.data["overall"] == "needs_review"


def test_agent_failure_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "agent_provider", "agenticorg")
    monkeypatch.setattr(settings, "agenticorg_api_key", "ao_sk_test")

    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(agent_client.httpx, "post", boom)
    out = saathi.check_compliance(["E-cigarette"], "IN", "AE")
    assert out.source == "fallback" and out.data["overall"] == "blocked"


def test_chat_drafts_send_order(client, make_user):
    u = make_user("Sunita Family")
    r = client.post("/api/agents/chat", headers=u["headers"], json={
        "message": "Please send 2 kg laddoos worth Rs 3000 to my son in Dubai from Pune by 5 Nov", "history": []})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["intent"] == "send_abroad"
    assert d["draft"]["destination_country"] == "AE" and d["draft"]["pickup_city"] == "Pune"
    assert d["draft"]["weight_kg"] == 2 and d["draft"]["needed_by"]
    assert d["draft"]["declared_value_inr"] == 3000
    assert d["estimate"]["price_paise"] == 66_000 and d["estimate"]["traveller_payout_paise"] == 60_000
    assert client.get("/api/agents/activity", headers=u["headers"]).json()


def test_compliance_token_and_blocking(client, make_user):
    u = make_user("Token Sender")
    bad = client.post("/api/shipments", headers=u["headers"], json={**SHIP, "item_name": "Vape pen"})
    assert bad.status_code == 422 and bad.json()["detail"]["blocked_items"] == ["Vape pen"]

    rep = client.post("/api/agents/compliance", headers=u["headers"],
                      json={"items": ["Silk saree"], "destination_country": "AE"}).json()
    assert rep["report"]["overall"] == "clear" and rep["token"]
    ok = client.post("/api/shipments", headers=u["headers"], json={**SHIP, "compliance_token": rep["token"]})
    assert ok.status_code == 201, ok.text
    assert ok.json()["compliance_report"]["items"][0]["status"] == "clear"
    # token for different items is ignored -> server re-checks
    other = client.post("/api/shipments", headers=u["headers"],
                        json={**SHIP, "item_name": "Gold bar", "compliance_token": rep["token"]})
    assert other.status_code == 422


def test_dabba_matching_negotiation_support(client, make_user, monkeypatch):
    sender, traveller = make_user("Dabba Sender"), make_user("Dabba Flyer")
    cur = client.post("/api/agents/dabbas/swadeshi-festive-wear/curate", headers=sender["headers"],
                      json={"country": "AE", "needed_by": (date.today() + timedelta(days=20)).isoformat()})
    assert cur.status_code == 200, cur.text
    draft = cur.json()["draft"]
    assert draft["kind"] == "send" and 0 < draft["weight_kg"] <= 3

    shp = client.post("/api/shipments", headers=sender["headers"], json={
        **SHIP, "item_name": draft["item_name"], "description": draft["description"], "weight_kg": draft["weight_kg"],
        "needed_by": draft["needed_by"], "compliance_ack": True}).json()
    trip = client.post("/api/trips", headers=traveller["headers"], json={
        "origin_city": "Mumbai", "origin_country": "IN", "destination_city": "Dubai", "destination_country": "AE",
        "travel_date": (date.today() + timedelta(days=5)).isoformat(), "capacity_kg": 10}).json()

    ranked = client.get(f"/api/agents/shipments/{shp['id']}/travellers", headers=sender["headers"]).json()
    assert [r["trip"]["id"] for r in ranked["ranked"]] == [trip["id"]]
    opp = client.get(f"/api/agents/trips/{trip['id']}/opportunities", headers=traveller["headers"]).json()
    assert any(o["kind"] == "shipment" and o["id"] == shp["id"] for o in opp["ranked"])

    neg = client.post("/api/agents/negotiate", headers=sender["headers"],
                      json={"item_value_inr": 20000, "source_country": "US"}).json()
    assert neg["min_inr"] <= neg["suggested_reward_inr"] <= neg["max_inr"]

    sup = client.post("/api/agents/support", headers=sender["headers"],
                      json={"kind": "shipment", "id": shp["id"], "question": "My parcel arrived damaged, refund?"})
    assert sup.status_code == 200 and sup.json()["escalate"] is True
    stranger = make_user("Stranger")
    assert client.post("/api/agents/support", headers=stranger["headers"],
                       json={"kind": "shipment", "id": shp["id"], "question": "where?"}).status_code == 404
    acts = client.get(f"/api/agents/activity?entity_type=shipment&entity_id={shp['id']}",
                      headers=sender["headers"]).json()
    assert any(a["agent"] == "tracking_support" and a["needs_human"] for a in acts)


def test_matching_keeps_agent_exclusions_visible(monkeypatch):
    def fake_run(agent, *args, **kwargs):
        return agent_client.AgentResult(agent=agent, ok=True, output={
            "ranked": [{"id": 2, "score": 88, "reason": "best date"}],
            "excluded": [{"id": 1, "reason": "packaging unclear"}]}, needs_human=False)

    monkeypatch.setattr(saathi, "run_agent", fake_run)
    out = saathi.rank_candidates("test", {}, [{"id": 1}, {"id": 2}, {"id": 3}], lambda c: (50, "rule"))
    ids = [r["id"] for r in out.data["ranked"]]
    assert ids == [2, 3, 1]
    assert out.data["ranked"][-1]["flagged"] and out.data["ranked"][-1]["score"] <= 20
    assert out.needs_human
