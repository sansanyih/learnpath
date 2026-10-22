"""Plan deletion: ownership + cascade cleanup."""

import pytest
from sqlalchemy import func, select

from app.db.database import SessionLocal
from app.db.models import (
    Annotation,
    Attempt,
    Chapter,
    ChapterProgress,
    ChapterQuiz,
    ChapterQuizAttempt,
    ChatMessage,
    Goal,
    KnowledgePoint,
    Mastery,
    Phase,
    Plan,
    PlanAdjustment,
    Quiz,
    RepoSource,
    ReviewItem,
    Task,
    TaskGuide,
    utcnow,
)


async def _register(client, email: str) -> tuple[str, str]:
    await client.post("/api/auth/register", json={"email": email, "password": "password123"})
    login = await client.post("/api/auth/login", json={"email": email, "password": "password123"})
    data = login.json()
    return data["token"], data["user"]["id"]


async def _seed_plan(user_id: str) -> str:
    async with SessionLocal() as db:
        goal = Goal(user_id=user_id, title="删除测试", raw_input="g", daily_minutes=45, level="beginner")
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
            title="t",
            type="reading",
            duration_min=20,
            resource="",
            acceptance="",
            repo_paths=[],
        )
        db.add(task)
        await db.flush()
        quiz = Quiz(
            plan_id=plan.id,
            phase_id=phase.id,
            kp_id=kp.id,
            type="choice",
            question="q",
            options=["a"],
            answer="A",
            explanation="",
            seq=1,
        )
        db.add(quiz)
        await db.flush()
        repo = RepoSource(
            plan_id=plan.id,
            repo_full_name="a/b",
            ref="main",
            commit_sha="x",
            file_count=1,
            status="ready",
        )
        db.add(repo)
        await db.flush()
        chapter = Chapter(
            plan_id=plan.id,
            repo_source_id=repo.id,
            seq=1,
            title="c",
            purpose="",
            files=[],
            concepts=[],
            status="ready",
        )
        db.add(chapter)
        await db.flush()
        chapter_quiz = ChapterQuiz(
            chapter_id=chapter.id,
            type="choice",
            question="chapter q",
            options=["a"],
            answer="A",
            explanation="",
            seq=1,
        )
        db.add(chapter_quiz)
        await db.flush()
        db.add(ChapterProgress(user_id=user_id, chapter_id=chapter.id, status="learning"))
        db.add(
            ChapterQuizAttempt(
                user_id=user_id,
                chapter_id=chapter.id,
                quiz_id=chapter_quiz.id,
                answer="A",
                score=100,
                dims={},
                feedback="",
            )
        )
        db.add(
            ChatMessage(
                user_id=user_id,
                scope="chapter",
                context_id=chapter.id,
                role="user",
                content="chapter chat",
            )
        )
        db.add(
            Annotation(
                user_id=user_id,
                scope="chapter",
                context_id=chapter.id,
                content="chapter note",
            )
        )
        db.add(
            ChatMessage(
                user_id=user_id,
                scope="task",
                context_id=task.id,
                role="user",
                content="task chat",
            )
        )
        db.add(
            Annotation(
                user_id=user_id,
                scope="task",
                context_id=task.id,
                content="task note",
            )
        )
        db.add(Attempt(user_id=user_id, quiz_id=quiz.id, phase_id=phase.id, answer="A", score=100, dims={}, feedback=""))
        db.add(Mastery(user_id=user_id, kp_id=kp.id, score=0.8, status="learning", attempts=1))
        db.add(ReviewItem(user_id=user_id, kp_id=kp.id, due_at=utcnow()))
        db.add(PlanAdjustment(user_id=user_id, plan_id=plan.id, phase_id=phase.id, action="review", payload={}))
        db.add(TaskGuide(task_id=task.id, user_id=user_id, payload={"steps": ["a"]}))
        await db.commit()
        return plan.id


async def test_delete_plan_cascades(client):
    token, user_id = await _register(client, "delete@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    plan_id = await _seed_plan(user_id)

    resp = await client.delete(f"/api/plans/{plan_id}", headers=headers)
    assert resp.status_code == 204

    missing = await client.get(f"/api/plans/{plan_id}", headers=headers)
    assert missing.status_code == 404
    listing = await client.get("/api/plans", headers=headers)
    assert listing.json() == []

    async with SessionLocal() as db:
        for model in (
            Plan,
            Goal,
            Phase,
            KnowledgePoint,
            Task,
            Quiz,
            Attempt,
            RepoSource,
            Chapter,
            ChapterProgress,
            ChapterQuiz,
            ChapterQuizAttempt,
            ChatMessage,
            Annotation,
            Mastery,
            ReviewItem,
            PlanAdjustment,
            TaskGuide,
        ):
            count = await db.scalar(select(func.count()).select_from(model))
            assert count == 0, model.__name__


async def test_delete_plan_is_owner_scoped(client):
    owner_token, owner_id = await _register(client, "owner-del@example.com")
    other_token, _ = await _register(client, "other-del@example.com")
    plan_id = await _seed_plan(owner_id)

    denied = await client.delete(
        f"/api/plans/{plan_id}", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert denied.status_code == 404

    still_there = await client.get(
        f"/api/plans/{plan_id}", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert still_there.status_code == 200
