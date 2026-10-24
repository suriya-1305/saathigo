from datetime import date

from app.services.boarding_pass import parse_boarding_pass_text, verify

TODAY = date(2026, 10, 24)


def test_parses_printed_boarding_pass():
    text = """INDIGO  BOARDING PASS
    NAME OF PASSENGER: SHARMA/RAHUL MR
    FROM BLR TO DXB
    FLIGHT 6E 1485   DATE 26 OCT 2026
    GATE 12  SEAT 14A"""
    data = parse_boarding_pass_text(text, TODAY)
    assert (data.origin_code, data.destination_code) == ("BLR", "DXB")
    assert data.flight_number == "6E1485"
    assert data.travel_date == date(2026, 10, 26)
    assert data.passenger_name == "SHARMA RAHUL"
    result = verify(data, "Rahul Sharma", TODAY)
    assert result.score == 100


def test_parses_bcbp_payload():
    payload = "M1" + "SHARMA/RAHUL".ljust(20) + "E" + "ABC123".ljust(7) + "DXB" + "BLR" + "EK ".ljust(3) \
        + "0566 " + "300" + "Y014A0001 100"
    data = parse_boarding_pass_text(f"some noise\n{payload}\n", TODAY)
    assert data.source == "bcbp"
    assert (data.origin_code, data.destination_code) == ("DXB", "BLR")
    assert data.flight_number == "EK566"
    assert data.travel_date == date(2026, 10, 27)


def test_parses_city_names_and_route_arrow():
    text = "Emirates\nDUBAI -> BENGALURU\nEK 568  27/10/2026\nPassenger: Priya Nair"
    data = parse_boarding_pass_text(text, TODAY)
    assert (data.origin_code, data.destination_code) == ("DXB", "BLR")
    assert data.flight_number == "EK568"
    assert data.travel_date == date(2026, 10, 27)


def test_low_score_when_unreadable():
    data = parse_boarding_pass_text("blurry nonsense text", TODAY)
    assert verify(data, "Rahul", TODAY).score < 60
