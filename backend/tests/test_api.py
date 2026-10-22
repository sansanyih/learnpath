"""M0 smoke tests: health, auth lifecycle, error envelope, mock SSE."""

import pytest

from app.services import plan_service

REGISTER = {"email": "m0@example.com", "password": "password123"}


class DisabledLlm:
    enabled = False


@pytest.fixture
def mock_llm(monkeypatch):
    monkeypatch.setattr(plan_service, "get_llm", lambda: DisabledLlm())


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_register_login_me(client):
    resp = await client.post("/api/auth/register", json=REGISTER)
    assert resp.status_code == 201
    assert resp.json()["email"] == "m0@example.com"

    resp = await client.post("/api/auth/login", json=REGISTER)
    assert resp.status_code == 200
    token = resp.json()["token"]

    resp = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "m0@example.com"


async def test_duplicate_email_returns_error_envelope(client):
    await client.post("/api/auth/register", json=REGISTER)
    resp = await client.post("/api/auth/register", json=REGISTER)
    assert resp.status_code == 409
    body = resp.json()
    assert body["error"]["code"] == "EMAIL_TAKEN"


async def test_wrong_password(client):
    await client.post("/api/auth/register", json=REGISTER)
    resp = await client.post(
        "/api/auth/login", json={"email": REGISTER["email"], "password": "wrong-password"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "BAD_CREDENTIALS"


async def test_me_requires_token(client):
    resp = await client.get("/api/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


async def test_validation_error(client):
    resp = await client.post("/api/plans/stream", json={"goal": "x", "daily_minutes": 5})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_plan_stream_mock(client, mock_llm):
    resp = await client.post(
        "/api/plans/stream",
        json={"goal": "三个月掌握 FastAPI 后端开发", "daily_minutes": 45},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "event: phase_skeleton" in resp.text
    assert "event: done" in resp.text
