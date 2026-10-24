from datetime import date, timedelta

import pytest

from app.api.routes import trips as trips_route
from app.core.config import settings
from tests.conftest import png_bytes


def _flight_text(name: str, origin: str, dest: str) -> str:
    d = (date.today() + timedelta(days=2)).strftime("%d %b %Y").upper()
    return f"BOARDING PASS\nNAME OF PASSENGER: {name.upper()}\nFROM {origin} TO {dest}\nFLIGHT EK 512  DATE {d}"


def _verified_trip(client, user, origin, dest, monkeypatch, file_bytes=None) -> dict:
    monkeypatch.setattr(trips_route.bp, "extract_text", lambda *a, **k: _flight_text(user["name"], origin, dest))
    scan = client.post("/api/trips/scan-boarding-pass", headers=user["headers"],
                       files={"file": ("bp.png", file_bytes or png_bytes(), "image/png")})
    assert scan.status_code == 200, scan.text
    s = scan.json()
    assert s["verified"], s
    trip = client.post("/api/trips", headers=user["headers"], json={
        "origin_city": s["origin_city"], "origin_country": s["origin_country"],
        "destination_city": s["destination_city"], "destination_country": s["destination_country"],
        "travel_date": s["travel_date"], "capacity_kg": 10, "scan_token": s["scan_token"],
    })
    assert trip.status_code == 201, trip.text
    assert trip.json()["verified"] is True
    return trip.json()


def _pay(client, user, purpose, ref_id):
    r = client.post("/api/payments/checkout", headers=user["headers"],
                    json={"purpose": purpose, "reference_id": ref_id})
    assert r.status_code == 200, r.text
    pid = r.json()["payment_id"]
    r = client.post(f"/api/payments/mock/checkout/{pid}/complete", data={"result": "success"},
                    follow_redirects=False)
    assert r.status_code == 303
    r = client.get(f"/api/payments/callback?payment_id={pid}", follow_redirects=False)
    assert r.status_code == 303 and "payments/result" in r.headers["location"]
    assert client.get(f"/api/payments/{pid}", headers=user["headers"]).json()["status"] == "success"


def test_buy_from_overseas_flow(client, make_user):
    buyer, traveller = make_user("Asha Buyer"), make_user("Ravi Traveller")

    r = client.post("/api/requests", headers=buyer["headers"], json={
        "product_url": "https://www.amazon.ae/dp/B0TEST", "title": "AirPods Pro", "price_amount": 899,
        "price_currency": "AED", "source_country": "AE", "deliver_city": "Bengaluru",
    })
    assert r.status_code == 201, r.text
    req = r.json()
    items = req["item_price_paise"] * req["quantity"]
    assert req["reward_paise"] == round(items * 0.20)        # traveller earns 20% of the product value
    assert req["service_fee_paise"] == round(items * 0.02)   # SaathiGo keeps 2%
    assert req["total_paise"] == items + req["reward_paise"] + req["service_fee_paise"]

    groups = client.get("/api/requests/grouped").json()
    assert any(g["country"] == "AE" and g["count"] >= 1 for g in groups)

    # No boarding pass or pre-created trip needed: offering records a trip automatically
    r = client.post(f"/api/requests/{req['id']}/offers", headers=traveller["headers"],
                    json={"reward_inr": 99999, "message": "Flying next week"})
    assert r.status_code == 201, r.text
    offer = r.json()
    assert offer["reward_paise"] == req["reward_paise"]  # reward is fixed, not negotiable
    assert offer["trip"]["origin_country"] == "AE" and offer["trip"]["destination_country"] == "IN"

    r = client.post(f"/api/requests/{req['id']}/offers/{offer['id']}/accept", headers=buyer["headers"])
    assert r.json()["status"] == "accepted"

    _pay(client, buyer, "product_request", req["id"])
    detail = client.get(f"/api/requests/{req['id']}", headers=buyer["headers"]).json()
    assert detail["status"] == "paid" and detail["delivery_otp"]
    otp = detail["delivery_otp"]
    assert client.get(f"/api/requests/{req['id']}", headers=traveller["headers"]).json()["delivery_otp"] is None

    r = client.post(f"/api/requests/{req['id']}/purchased", headers=traveller["headers"],
                    files={"photo": ("p.png", png_bytes(), "image/png")})
    assert r.json()["status"] == "purchased"

    assert client.post(f"/api/requests/{req['id']}/deliver", headers=traveller["headers"],
                       data={"otp": "000000" if otp != "000000" else "111111"}).status_code == 400
    r = client.post(f"/api/requests/{req['id']}/deliver", headers=traveller["headers"], data={"otp": otp})
    assert r.json()["status"] == "delivered"
    payouts = client.get("/api/payouts/mine", headers=traveller["headers"]).json()
    assert payouts[0]["amount_paise"] == items + req["reward_paise"]


def test_send_overseas_flow(client, make_user):
    sender, traveller = make_user("Meera Sender"), make_user("Kiran Flyer")

    # Simple listing: what, value, from, to. Homemade food only gets a packaging note, it is not blocked.
    r = client.post("/api/shipments", headers=sender["headers"], json={
        "item_name": "Homemade snacks", "declared_value_inr": 2000, "pickup_city": "Bengaluru",
        "destination_country": "US", "destination_city": "San Francisco",
    })
    assert r.status_code == 201, r.text
    shp = r.json()
    assert shp["compliance_status"] == "needs_review"
    assert shp["traveller_payout_paise"] == 40_000 and shp["price_paise"] == 44_000  # 20% + 2% of Rs 2,000

    # Everyone (even logged out) sees it under its destination
    groups = client.get("/api/shipments/grouped").json()
    assert any(g["country"] == "US" and any(i["id"] == shp["id"] for i in g["items"]) for g in groups)
    assert client.get(f"/api/shipments/{shp['id']}").json()["recipient_address"] is None

    assert client.post(f"/api/shipments/{shp['id']}/accept", headers=sender["headers"], json={}).status_code == 400
    r = client.post(f"/api/shipments/{shp['id']}/accept", headers=traveller["headers"], json={})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "matched" and r.json()["trip"]["destination_country"] == "US"
    assert client.post(f"/api/shipments/{shp['id']}/accept", headers=make_user("Late")["headers"],
                       json={}).status_code == 409

    # Cannot hand over before payment
    assert client.post(f"/api/shipments/{shp['id']}/handover", headers=traveller["headers"],
                       files={"photo": ("h.png", png_bytes(), "image/png")}).status_code == 409

    _pay(client, sender, "shipment", shp["id"])
    sender_view = client.get(f"/api/shipments/{shp['id']}", headers=sender["headers"]).json()
    assert sender_view["status"] == "paid" and sender_view["delivery_otp"]

    r = client.post(f"/api/shipments/{shp['id']}/handover", headers=traveller["headers"],
                    files={"photo": ("h.png", png_bytes(), "image/png")})
    assert r.json()["status"] == "in_transit"
    assert r.json()["handover_photo_url"].startswith("/uploads/")
    assert client.get(r.json()["handover_photo_url"]).status_code == 200

    r = client.post(f"/api/shipments/{shp['id']}/deliver", headers=traveller["headers"],
                    data={"otp": sender_view["delivery_otp"]})
    assert r.json()["status"] == "delivered"
    payouts = client.get("/api/payouts/mine", headers=traveller["headers"]).json()
    assert payouts[0]["amount_paise"] == shp["traveller_payout_paise"]


def test_boarding_pass_is_off_by_default(client, make_user):
    u = make_user("No Scan")
    r = client.post("/api/trips/scan-boarding-pass", headers=u["headers"],
                    files={"file": ("bp.png", png_bytes(), "image/png")})
    assert r.status_code == 404


def test_boarding_pass_when_enabled(client, make_user, monkeypatch):
    monkeypatch.setattr(settings, "boarding_pass_enabled", True)
    a, b = make_user("Same Person"), make_user("Same Person")
    buyer = make_user("Strict Buyer")
    req = client.post("/api/requests", headers=buyer["headers"], json={
        "product_url": "https://www.harrods.com/x", "title": "Tea set", "price_amount": 50,
        "price_currency": "GBP", "source_country": "GB", "deliver_city": "Delhi"}).json()
    # Without a verified trip the traveller is asked to verify first
    assert client.post(f"/api/requests/{req['id']}/offers", headers=a["headers"], json={}).status_code == 403
    same_file = png_bytes() + b"reuse"
    trip = _verified_trip(client, a, "LHR", "DEL", monkeypatch, file_bytes=same_file)
    r = client.post(f"/api/requests/{req['id']}/offers", headers=a["headers"], json={"trip_id": trip["id"]})
    assert r.status_code == 201, r.text
    monkeypatch.setattr(trips_route.bp, "extract_text", lambda *a_, **k: _flight_text("Same Person", "LHR", "DEL"))
    scan = client.post("/api/trips/scan-boarding-pass", headers=b["headers"],
                       files={"file": ("bp.png", same_file, "image/png")}).json()
    assert scan["verified"] is False


def test_assistant_answers_about_my_orders(client, make_user):
    u = make_user("Popup User")
    shp = client.post("/api/shipments", headers=u["headers"], json={
        "item_name": "Silk kurta", "declared_value_inr": 3000, "pickup_city": "Pune",
        "destination_country": "GB", "destination_city": "London"}).json()
    r = client.post("/api/agents/assistant", headers=u["headers"],
                    json={"message": f"Where is my order S{shp['id']}?"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert f"S{shp['id']}" in d["reply"] and d["links"][0]["path"] == f"/send/{shp['id']}"
    anon = client.post("/api/agents/assistant", json={"message": "What can I carry to London?"}).json()
    assert "United Kingdom" in anon["reply"]
    fee = client.post("/api/agents/assistant", json={"message": "How much is the fee?"}).json()
    assert "20%" in fee["reply"] and "2%" in fee["reply"]

@pytest.mark.parametrize("path", ["/api/requests/mine", "/api/shipments/mine", "/api/trips/mine"])
def test_auth_required(client, path):
    assert client.get(path).status_code == 401
