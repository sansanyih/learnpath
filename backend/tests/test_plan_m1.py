"""M1 tests: generation pipeline with a fake LLM (no network)."""

import json
import re

import pytest

from app.llm.client import LlmError, LlmResult
from app.services import plan_service

SKELETON = {
    "phases": [
        {
            "id": f"p{i}",
            "title": f"阶段 {i}",
            "days": 7,
            "focus": f"阶段 {i} 的目标",
            "prerequisites": [] if i == 1 else [f"p{i - 1}"],
            "knowledge_points": [
                {"name": f"知识点 {i}-{j}", "objective": f"能讲清 {i}-{j}"} for j in range(1, 4)
            ],
            "deliverable": f"交付物 {i}",
        }
        for i in range(1, 5)
    ],
    "assumptions": ["测试环境"],
}

DETAIL = {
    "tasks": [
        {
            "day_offset": j,
            "title": f"任务 {j + 1}",
            "type": "coding" if j % 2 == 0 else "reading",
            "duration_min": 30,
            "resource": "docs",
            "acceptance": "能复现",
        }
        for j in range(5)
    ]
}


class FakeLlm:
    enabled = True

    def __init__(self) -> None:
        self.calls = 0

    async def chat_json(self, system, user, temperature=0.3, max_tokens=2048):
        self.calls += 1
        if "用户目标" in user:
            data = SKELETON
        else:
            match = re.search(r'"days":\s*(\d+)', user)
            days = int(match.group(1)) if match else 5
            data = {
                "tasks": [
                    {
                        "day_offset": day,
                        "title": f"任务 {day + 1}",
                        "type": "coding" if day % 2 == 0 else "reading",
                        "duration_min": 30,
                        "resource": "docs",
                        "acceptance": "能复现",
                    }
                    for day in range(days)
                ]
            }
        return LlmResult(text=json.dumps(data, ensure_ascii=False), tokens_in=120, tokens_out=60, latency_ms=5)


class FallbackDetailLlm(FakeLlm):
    """Skeleton is valid, phase detail always fails -> fallback tasks."""

    async def chat_json(self, system, user, temperature=0.3, max_tokens=2048):
        self.calls += 1
        if "用户目标" in user:
            return LlmResult(text=json.dumps(SKELETON, ensure_ascii=False), tokens_in=100, tokens_out=50)
        raise LlmError("INVALID_OUTPUT", "detail broken")


@pytest.fixture
def fake_llm(monkeypatch):
    fake = FakeLlm()
    monkeypatch.setattr(plan_service, "get_llm", lambda: fake)
    return fake


async def _register(client, email: str) -> str:
    await client.post("/api/auth/register", json={"email": email, "password": "password123"})
    login = await client.post("/api/auth/login", json={"email": email, "password": "password123"})
    return login.json()["token"]


def _plan_id(text: str) -> str | None:
    match = re.search(r'"plan_id":\s*"([0-9a-f-]{36})"', text)
    return match.group(1) if match else None


async def test_generate_persists_and_reads_back(client, fake_llm):
    token = await _register(client, "m1@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/plans/stream",
        json={"goal": "三个月掌握 FastAPI 后端开发", "daily_minutes": 45},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.text
    assert "event: phase_skeleton" in body
    assert "event: phase_detail" in body
    assert "event: done" in body

    plan_id = _plan_id(body)
    assert plan_id, body[-500:]

    detail = await client.get(f"/api/plans/{plan_id}", headers=headers)
    assert detail.status_code == 200
    data = detail.json()
    assert data["status"] == "ready"
    assert len(data["phases"]) == 4
    assert all(len(phase["tasks"]) == phase["days"] for phase in data["phases"])
    assert data["phases"][0]["seq"] == 1

    plans = await client.get("/api/plans", headers=headers)
    assert plans.status_code == 200
    assert len(plans.json()) == 1
    assert plans.json()[0]["task_count"] == sum(phase["days"] for phase in data["phases"])


async def test_guest_gets_skeleton_only(client, fake_llm):
    resp = await client.post(
        "/api/plans/stream",
        json={"goal": "三个月掌握 FastAPI 后端开发", "daily_minutes": 45},
    )
    assert resp.status_code == 200
    body = resp.text
    assert "event: phase_skeleton" in body
    assert "event: phase_detail" not in body
    assert '"plan_id": null' in body or '"plan_id":null' in body


async def test_plan_detail_is_scoped_to_owner(client, fake_llm):
    owner = await _register(client, "owner@example.com")
    other = await _register(client, "other@example.com")

    resp = await client.post(
        "/api/plans/stream",
        json={"goal": "三个月掌握 FastAPI 后端开发", "daily_minutes": 45},
        headers={"Authorization": f"Bearer {owner}"},
    )
    plan_id = _plan_id(resp.text)
    assert plan_id

    denied = await client.get(f"/api/plans/{plan_id}", headers={"Authorization": f"Bearer {other}"})
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "PLAN_NOT_FOUND"


async def test_usage_is_recorded(client, fake_llm):
    token = await _register(client, "usage@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/plans/stream",
        json={"goal": "三个月掌握 FastAPI 后端开发", "daily_minutes": 45},
        headers=headers,
    )
    assert '"cost_est"' in resp.text

    from sqlalchemy import func, select

    from app.db.database import SessionLocal
    from app.db.models import LlmUsage

    async with SessionLocal() as db:
        count = await db.scalar(select(func.count()).select_from(LlmUsage))
    assert count is not None and count >= 5


async def test_guest_daily_limit(client, fake_llm):
    payload = {"goal": "三个月掌握 FastAPI 后端开发", "daily_minutes": 45}
    for _ in range(5):
        resp = await client.post(
            "/api/plans/stream", json=payload, headers={"X-Guest-Id": "guest-limit-test"}
        )
        assert resp.status_code == 200

    blocked = await client.post(
        "/api/plans/stream", json=payload, headers={"X-Guest-Id": "guest-limit-test"}
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "GUEST_LIMIT_REACHED"


async def test_phase_detail_falls_back_to_tasks(client, monkeypatch):
    fake = FallbackDetailLlm()
    monkeypatch.setattr(plan_service, "get_llm", lambda: fake)

    token = await _register(client, "fallback@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        "/api/plans/stream",
        json={"goal": "三个月掌握 FastAPI 后端开发", "daily_minutes": 45},
        headers=headers,
    )
    body = resp.text
    assert '"fallback_phases": 4' in body

    plan_id = _plan_id(body)
    detail = await client.get(f"/api/plans/{plan_id}", headers=headers)
    data = detail.json()
    assert all(len(phase["tasks"]) == phase["days"] for phase in data["phases"])
