"""M3 tests: quiz generation, grading, mastery, adjustment, task toggle."""

import json

import pytest
from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import (
    Attempt,
    Chapter,
    Goal,
    KnowledgePoint,
    Mastery,
    Phase,
    Plan,
    Task,
    User,
)
from app.llm.client import LlmResult
from app.services import quiz_service

QUIZ = {
    "questions": [
        {
            "type": "choice",
            "question": "关于知识点 1-1，下面哪个说法正确？",
            "options": ["a", "b", "c", "d"],
            "answer": "A",
            "explanation": "",
            "kp": "知识点 1-1",
        },
        {
            "type": "choice",
            "question": "关于知识点 1-2，下面哪个说法正确？",
            "options": ["a", "b", "c", "d"],
            "answer": "A",
            "explanation": "",
            "kp": "知识点 1-2",
        },
        {
            "type": "choice",
            "question": "关于知识点 1-3，下面哪个说法正确？",
            "options": ["a", "b", "c", "d"],
            "answer": "A",
            "explanation": "",
            "kp": "知识点 1-3",
        },
        {"type": "open", "question": "请用自己的话解释知识点 1-1 的机制。", "answer": "参考", "explanation": "", "kp": "知识点 1-1"},
        {"type": "open", "question": "请用自己的话解释知识点 1-2 的用途。", "answer": "参考", "explanation": "", "kp": "知识点 1-2"},
    ]
}

GRADE = {
    "score": 30,
    "dims": {"technical": 30, "principle": 30, "coverage": 30, "structure": 30},
    "feedback": "结论不完整，补充因果链。",
}


class QuizLlm:
    enabled = True

    async def chat_json(self, system, user, temperature=0.3, max_tokens=2048):
        if "阶段信息" in user:
            text = json.dumps(QUIZ, ensure_ascii=False)
        else:
            text = json.dumps(GRADE, ensure_ascii=False)
        return LlmResult(text=text, tokens_in=200, tokens_out=100, latency_ms=5)


@pytest.fixture
def quiz_llm(monkeypatch):
    fake = QuizLlm()
    monkeypatch.setattr(quiz_service, "get_llm", lambda: fake)
    return fake


async def _seed_phase(email: str = "quiz@example.com"):
    async with SessionLocal() as db:
        user = User(email=email, password_hash="x")
        db.add(user)
        await db.flush()
        goal = Goal(user_id=user.id, title="g", raw_input="g", daily_minutes=45, level="beginner")
        db.add(goal)
        await db.flush()
        plan = Plan(goal_id=goal.id, status="ready")
        db.add(plan)
        await db.flush()
        phase = Phase(plan_id=plan.id, seq=1, title="阶段一", days=7, focus="f", deliverable="d")
        db.add(phase)
        await db.flush()
        for index in range(1, 4):
            db.add(
                KnowledgePoint(
                    phase_id=phase.id,
                    name=f"知识点 1-{index}",
                    objective="o",
                    seq=index,
                )
            )
        task = Task(
            phase_id=phase.id,
            day_offset=0,
            title="任务 A",
            type="reading",
            duration_min=20,
            resource="",
            acceptance="",
            repo_paths=[],
        )
        db.add(task)
        await db.commit()
        return user.id, plan.id, phase.id, task.id


async def test_quiz_generation_grading_and_adjustment(client, quiz_llm):
    user_id, plan_id, phase_id, _task_id = await _seed_phase()

    quiz = await quiz_service.get_or_create_phase_quiz(plan_id, phase_id, user_id)
    assert len(quiz["questions"]) == 5
    assert sum(1 for q in quiz["questions"] if q["type"] == "choice") == 3

    answers = [
        {"quiz_id": q["id"], "answer": "B" if q["type"] == "choice" else "不会"}
        for q in quiz["questions"]
    ]
    result = await quiz_service.submit_phase_quiz(phase_id, user_id, answers)

    assert result["score"] == 12
    assert result["adjustment"]["action"] == "remediate_plus"
    assert len(result["adjustment"]["tasks"]) == 3

    adopted = await quiz_service.adopt_adjustment(result["adjustment"]["id"], user_id)
    assert adopted["inserted"] == 3

    async with SessionLocal() as db:
        mastery = (await db.scalars(select(Mastery).where(Mastery.user_id == user_id))).all()
        attempts = (await db.scalars(select(Attempt).where(Attempt.user_id == user_id))).all()
        tasks = (await db.scalars(select(Task).where(Task.phase_id == phase_id))).all()
        phase = await db.get(Phase, phase_id)
    assert len(mastery) == 3
    assert len(attempts) == 5
    assert len(tasks) == 4
    assert phase.status == "doing"


async def test_task_toggle_updates_phase(client):
    from app.api import deps

    _user_id, _plan_id, phase_id, task_id = await _seed_phase("toggle@example.com")

    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == "toggle@example.com"))
        from app.core.config import get_settings
        from app.core.security import create_access_token

        token = create_access_token(user.id, user.token_version, get_settings())

    headers = {"Authorization": f"Bearer {token}"}
    response = await client.patch(f"/api/tasks/{task_id}", json={"status": "done"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["phase_status"] == "done"

    async with SessionLocal() as db:
        task = await db.get(Task, task_id)
    assert task.status == "done"
