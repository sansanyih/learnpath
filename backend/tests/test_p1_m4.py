"""P1: login lockout, token quota, export/delete, stats, review streak."""

from datetime import timedelta

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import (
    Goal,
    KnowledgePoint,
    LlmUsage,
    Mastery,
    Phase,
    Plan,
    ReviewItem,
    Task,
    User,
    utcnow,
)


async def _register(client, email: str) -> tuple[str, str]:
    await client.post("/api/auth/register", json={"email": email, "password": "password123"})
    login = await client.post("/api/auth/login", json={"email": email, "password": "password123"})
    data = login.json()
    return data["token"], data["user"]["id"]


async def test_login_lockout_after_failures(client):
    await client.post("/api/auth/register", json={"email": "lock@example.com", "password": "password123"})
    for _ in range(5):
        bad = await client.post(
            "/api/auth/login", json={"email": "lock@example.com", "password": "wrong-password"}
        )
        assert bad.status_code == 401

    locked = await client.post(
        "/api/auth/login", json={"email": "lock@example.com", "password": "password123"}
    )
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "LOGIN_LOCKED"


async def test_export_and_soft_delete(client):
    token, _ = await _register(client, "account@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    export = await client.get("/api/me/export", headers=headers)
    assert export.status_code == 200
    assert export.json()["user"]["email"] == "account@example.com"

    deleted = await client.delete("/api/me", headers=headers)
    assert deleted.status_code == 200
    assert (await client.get("/api/me", headers=headers)).status_code == 401

    recovered = await client.post(
        "/api/auth/login", json={"email": "account@example.com", "password": "password123"}
    )
    assert recovered.status_code == 200


async def test_token_quota_blocks_plan_generation(client):
    token, user_id = await _register(client, "quota@example.com")
    async with SessionLocal() as db:
        db.add(
            LlmUsage(
                user_id=user_id,
                purpose="test",
                model="test",
                tokens_in=60000,
                tokens_out=0,
                cost_est=0,
                latency_ms=0,
                ok=True,
            )
        )
        await db.commit()

    resp = await client.post(
        "/api/plans/stream",
        json={"goal": "三个月掌握 Python", "daily_minutes": 45, "level": "beginner"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "USER_QUOTA_EXCEEDED"


async def test_stats_and_three_streak_mastery(client):
    token, user_id = await _register(client, "stats@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    async with SessionLocal() as db:
        goal = Goal(user_id=user_id, title="stats", raw_input="g", daily_minutes=45, level="beginner")
        db.add(goal)
        await db.flush()
        plan = Plan(goal_id=goal.id, status="ready")
        db.add(plan)
        await db.flush()
        phase = Phase(plan_id=plan.id, seq=1, title="p", days=7, focus="", deliverable="")
        db.add(phase)
        await db.flush()
        kp = KnowledgePoint(phase_id=phase.id, name="kp", objective="o", seq=1)
        db.add(kp)
        await db.flush()
        task = Task(
            phase_id=phase.id,
            day_offset=0,
            title="完成的任务",
            type="reading",
            duration_min=45,
            resource="",
            acceptance="",
            repo_paths=[],
            status="done",
            completed_at=utcnow(),
        )
        db.add(task)
        review = ReviewItem(user_id=user_id, kp_id=kp.id, due_at=utcnow() - timedelta(hours=1))
        db.add(review)
        db.add(Mastery(user_id=user_id, kp_id=kp.id, score=0.5, status="learning", attempts=1))
        await db.commit()
        review_id = review.id

    stats = await client.get("/api/stats", headers=headers)
    assert stats.status_code == 200
    body = stats.json()
    assert body["streak"] >= 1
    assert body["week"]["minutes"] >= 45
    assert body["review_strategy"]["intervals"] == [1, 3, 7, 15, 30]

    last = None
    for _ in range(3):
        last = await client.post(
            f"/api/reviews/{review_id}/complete", headers=headers, json={"result": "good"}
        )
        assert last.status_code == 200
    assert last.json()["streak"] == 3
    assert last.json()["mastered"] is True

    async with SessionLocal() as db:
        mastery = await db.scalar(
            select(Mastery).where(Mastery.user_id == user_id, Mastery.kp_id == kp.id)
        )
    assert mastery.status == "mastered"
