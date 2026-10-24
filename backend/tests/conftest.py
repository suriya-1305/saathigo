import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="tagalong-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")
os.environ["PAYMENT_PROVIDER"] = "mock"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256"
os.environ["BACKEND_URL"] = "http://testserver"
os.environ["AGENT_PROVIDER"] = "mock"  # never hit AgenticOrg from tests; rule-based fallbacks answer

import io  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 30, 30)).save(buf, "PNG")
    return buf.getvalue()


_counter = {"n": 0}


@pytest.fixture
def make_user(client):
    def _make(name: str) -> dict:
        _counter["n"] += 1
        email = f"user{_counter['n']}@example.com"
        r = client.post("/api/auth/register", json={"name": name, "email": email, "password": "password123",
                                                    "phone": "9876543210", "city": "Bengaluru"})
        assert r.status_code == 201, r.text
        return {"headers": {"Authorization": f"Bearer {r.json()['access_token']}"}, **r.json()["user"]}
    return _make
