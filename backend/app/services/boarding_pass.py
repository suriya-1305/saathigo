"""Boarding pass processing.

Privacy model: the uploaded file is processed fully in memory and discarded as soon as
the request ends. Only the parsed route/flight/date and a SHA-256 fingerprint (to detect
the same pass being reused by another account) are ever persisted.
"""

from __future__ import annotations

import hashlib
import io
import re
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from app.core.config import settings
from app.data.airports import AIRPORTS, CITY_ALIASES

MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1)}

AIRLINE_CODES = {
    "6E", "AI", "IX", "UK", "SG", "G8", "QP", "I5", "EK", "QR", "EY", "FZ", "G9", "WY", "GF", "KU", "SV",
    "J9", "OV", "SQ", "TR", "MH", "AK", "OD", "TG", "CX", "UL", "JL", "NH", "CA", "MU", "LH", "BA", "VS",
    "AF", "KL", "LX", "TK", "UA", "AA", "DL", "AC", "QF", "NZ", "VA", "EI", "IB", "AZ", "SU", "ET", "MS",
}
# 3-letter airport codes that are also common English words; only trusted in explicit route patterns.
AMBIGUOUS_CODES = {"MAN", "PER", "BER", "ADL"}


class OcrUnavailableError(RuntimeError):
    pass


class UnreadableFileError(ValueError):
    pass


@dataclass
class BoardingPassData:
    passenger_name: str | None = None
    origin_code: str | None = None
    destination_code: str | None = None
    flight_number: str | None = None
    travel_date: date | None = None
    source: str = "text"

    @property
    def origin(self) -> tuple[str, str] | None:
        return AIRPORTS.get(self.origin_code or "")

    @property
    def destination(self) -> tuple[str, str] | None:
        return AIRPORTS.get(self.destination_code or "")


@dataclass
class VerificationResult:
    score: int
    checks: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def fingerprint(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# ---------------------------------------------------------------- text extraction

def extract_text(content: bytes, content_type: str | None, filename: str | None = None) -> str:
    is_pdf = (content_type or "").endswith("pdf") or (filename or "").lower().endswith(".pdf") \
        or content.startswith(b"%PDF")
    if is_pdf:
        return _extract_pdf(content)
    return _ocr_image_bytes(content)


def _extract_pdf(content: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:3])
    except Exception as exc:  # pypdf raises many exception types for malformed files
        raise UnreadableFileError("Could not read PDF") from exc
    if len(text.strip()) >= 20:
        return text
    # Scanned/image-only PDF: OCR the embedded images.
    chunks: list[str] = []
    for page in reader.pages[:2]:
        for img in page.images:
            chunks.append(_ocr_image_bytes(img.data))
    return "\n".join(chunks)


def _ocr_image_bytes(content: bytes) -> str:
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        import pytesseract
    except ImportError as exc:
        raise OcrUnavailableError("pytesseract is not installed") from exc
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    try:
        image = Image.open(io.BytesIO(content))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise UnreadableFileError("Unsupported or corrupt image") from exc

    image = ImageOps.exif_transpose(image).convert("L")
    if image.width < 1400:
        scale = 1400 / image.width
        image = image.resize((int(image.width * scale), int(image.height * scale)))
    image = ImageOps.autocontrast(image)
    try:
        return pytesseract.image_to_string(image, config="--psm 6")
    except pytesseract.TesseractNotFoundError as exc:
        raise OcrUnavailableError(
            "Tesseract OCR binary not found. Install it and set TESSERACT_CMD."
        ) from exc
    finally:
        image.close()


# ---------------------------------------------------------------- parsing

def parse_boarding_pass_text(text: str, today: date | None = None) -> BoardingPassData:
    today = today or date.today()
    upper = text.upper()
    bcbp = _parse_bcbp(upper, today)
    if bcbp:
        return bcbp

    data = BoardingPassData(source="text")
    data.origin_code, data.destination_code = _find_route(upper)
    data.flight_number = _find_flight(upper)
    data.travel_date = _find_date(upper, today)
    data.passenger_name = _find_name(upper)
    return data


def _parse_bcbp(text: str, today: date) -> BoardingPassData | None:
    """IATA Resolution 792 Bar Coded Boarding Pass (when the barcode payload is present as text)."""
    idx = text.find("M1")
    while idx != -1:
        s = text[idx:]
        if len(s) >= 47:
            origin, dest = s[30:33], s[33:36]
            if origin.isalpha() and dest.isalpha() and origin in AIRPORTS and dest in AIRPORTS:
                carrier = s[36:39].strip()
                flight_no = s[39:44].strip().lstrip("0")
                julian = s[44:47]
                travel = None
                if julian.isdigit() and 1 <= int(julian) <= 366:
                    travel = date(today.year, 1, 1) + timedelta(days=int(julian) - 1)
                    if travel < today - timedelta(days=30):
                        travel = date(today.year + 1, 1, 1) + timedelta(days=int(julian) - 1)
                name = s[2:22].strip().replace("/", " ")
                return BoardingPassData(
                    passenger_name=name or None, origin_code=origin, destination_code=dest,
                    flight_number=f"{carrier}{flight_no}" if carrier and flight_no else None,
                    travel_date=travel, source="bcbp",
                )
        idx = text.find("M1", idx + 2)
    return None


def _find_route(text: str) -> tuple[str | None, str | None]:
    for a, b in re.findall(r"\b([A-Z]{3})\s*(?:-|–|—|→|>|TO|/)\s*([A-Z]{3})\b", text):
        if a in AIRPORTS and b in AIRPORTS and a != b:
            return a, b

    m = re.search(r"FROM\s*[:\-]?\s*([A-Z ]{3,30}?)\s*(?:\(([A-Z]{3})\))?\s*\n?.*?TO\s*[:\-]?\s*([A-Z ]{3,30}?)"
                  r"\s*(?:\(([A-Z]{3})\))?(?:\n|$)", text, re.S)
    if m:
        a = m.group(2) or _city_to_code(m.group(1))
        b = m.group(4) or _city_to_code(m.group(3))
        if a and b and a != b:
            return a, b

    found: list[tuple[int, str]] = []
    for match in re.finditer(r"\b([A-Z]{3})\b", text):
        code = match.group(1)
        if code in AIRPORTS and code not in AMBIGUOUS_CODES:
            found.append((match.start(), code))
    for city, code in CITY_ALIASES.items():
        for match in re.finditer(rf"\b{re.escape(city)}\b", text):
            found.append((match.start(), code))
    ordered: list[str] = []
    for _, code in sorted(found):
        if not ordered or (code not in ordered and AIRPORTS[code][0] != AIRPORTS[ordered[-1]][0]):
            ordered.append(code)
    if len(ordered) >= 2:
        return ordered[0], ordered[1]
    return (ordered[0] if ordered else None), None


def _city_to_code(raw: str) -> str | None:
    raw = raw.strip()
    if raw in AIRPORTS:
        return raw
    for city, code in CITY_ALIASES.items():
        if city in raw:
            return code
    return None


def _find_flight(text: str) -> str | None:
    m = re.search(r"\b(?:FLIGHT|FLT)\s*(?:NO\.?|NUMBER)?\s*[:\-]?\s*([A-Z0-9]{2})\s?-?(\d{1,4})\b", text)
    if m:
        return f"{m.group(1)}{int(m.group(2))}"
    for code, num in re.findall(r"\b([A-Z]{2}|[A-Z]\d|\d[A-Z])\s?-?(\d{2,4})\b", text):
        if code in AIRLINE_CODES:
            return f"{code}{int(num)}"
    return None


def _find_date(text: str, today: date) -> date | None:
    candidates: list[date] = []
    for d, mon, y in re.findall(r"\b(\d{1,2})\s?-?(" + "|".join(MONTHS) + r")[A-Z]*\s?-?(\d{2,4})?\b", text):
        year = _year(y, today)
        try:
            cand = date(year, MONTHS[mon], int(d))
        except ValueError:
            continue
        if not y and cand < today - timedelta(days=30):
            cand = cand.replace(year=cand.year + 1)
        candidates.append(cand)
    for y, mo, d in re.findall(r"\b(\d{4})-(\d{2})-(\d{2})\b", text):
        try:
            candidates.append(date(int(y), int(mo), int(d)))
        except ValueError:
            pass
    for d, mo, y in re.findall(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})\b", text):
        try:
            candidates.append(date(_year(y, today), int(mo), int(d)))
        except ValueError:
            pass
    if not candidates:
        return None
    plausible = [c for c in candidates if today - timedelta(days=2) <= c <= today + timedelta(days=365)]
    return (plausible or candidates)[0]


def _year(raw: str, today: date) -> int:
    if not raw:
        return today.year
    year = int(raw)
    return year + 2000 if year < 100 else year


def _find_name(text: str) -> str | None:
    m = re.search(r"(?:NAME OF PASSENGER|PASSENGER NAME|PASSENGER|NAME)\s*[:\-]?\s*\n?\s*([A-Z][A-Z /.]{2,40})", text)
    if not m:
        return None
    name = re.sub(r"\b(MR|MRS|MS|MSTR|MISS|DR)\b\.?", "", m.group(1)).replace("/", " ")
    name = re.sub(r"\s+", " ", name).strip()
    return name or None


# ---------------------------------------------------------------- verification

def verify(data: BoardingPassData, account_name: str, today: date | None = None) -> VerificationResult:
    today = today or date.today()
    checks: list[dict] = []
    score = 0

    route_ok = bool(data.origin and data.destination and data.origin_code != data.destination_code)
    checks.append({"label": "Route (origin & destination airports) detected", "ok": route_ok})
    score += 35 if route_ok else 0

    flight_ok = bool(data.flight_number)
    checks.append({"label": "Flight number detected", "ok": flight_ok})
    score += 15 if flight_ok else 0

    date_ok = data.travel_date is not None
    near = date_ok and today - timedelta(days=1) <= data.travel_date <= today + timedelta(days=7)
    checks.append({"label": "Travel date detected", "ok": date_ok})
    checks.append({"label": "Flight is within the next 7 days", "ok": bool(near)})
    score += 10 if date_ok else 0
    score += 20 if near else (5 if date_ok and data.travel_date >= today - timedelta(days=1) else 0)

    name_ok = _names_match(data.passenger_name, account_name)
    checks.append({"label": "Passenger name matches your profile", "ok": name_ok})
    score += 20 if name_ok else 0

    return VerificationResult(score=min(score, 100), checks=checks)


def _names_match(pass_name: str | None, account_name: str) -> bool:
    if not pass_name:
        return False
    a = {t for t in re.split(r"[\s/.]+", pass_name.upper()) if len(t) > 1}
    b = {t for t in re.split(r"[\s/.]+", account_name.upper()) if len(t) > 1}
    return bool(a & b)
