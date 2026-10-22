"""Task guide tests: generation, caching, ownership."""

import json

import pytest
from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Goal, Phase, Plan, Task, TaskGuide, User
from app.llm.client import LlmResult
from app.services import task_service

GUIDE = {
    "steps": [
        "先读官方文档的依赖注入一节，记下 Depends 的三种用法。",
        "手写一个最小示例，把参数校验和依赖注入连起来。",
        "用 curl 验证正常与异常两条路径，记录状态码。",
    ],
    "concepts": [
        {"name": "依赖注入", "explanation": "把参数的构造交给框架，调用方只声明需要什么，不关心怎么创建。"},
        {"name": "Depends", "explanation": "FastAPI 用来声明依赖的函数，请求进来时先执行依赖，再把结果注入参数。"},
    ],
    "code_examples": [
        {
            "title": "最小依赖",
            "language": "python",
            "code": "from fastapi import Depends, FastAPI\n\napp = FastAPI()\n\ndef common(q: str = \"\"):\n    return {\"q\": q}\n\n@app.get(\"/items\")\ndef items(common=Depends(common)):\n    return common",
            "note": "请求 /items?q=x 时，common 先执行，再把返回值注入 items。",
        }
    ],
    "materials": [
        {"title": "FastAPI 官方文档", "url": "https://fastapi.tiangolo.com/", "kind": "doc"}
    ],
    "search_queries": ["FastAPI Depends 用法", "FastAPI 依赖注入 示例"],
    "self_check": ["Depends 在请求生命周期里什么时候执行？", "依赖返回缓存了吗？"],
    "pitfalls": ["把依赖当中间件用"],
}


class GuideLlm:
    enabled = True

    def __init__(self) -> None:
        self.calls = 0

    async def chat_json(self, system, user, temperature=0.3, max_tokens=2048):
        self.calls += 1
        return LlmResult(text=json.dumps(GUIDE, ensure_ascii=False), tokens_in=100, tokens_out=80)


async def _seed_task(email: str):
    async with SessionLocal() as db:
        user = User(email=email, password_hash="x")
        db.add(user)
        await db.flush()
        goal = Goal(user_id=user.id, title="三个月掌握 Python", raw_input="g", daily_minutes=45, level="intermediate")
        db.add(goal)
        await db.flush()
        plan = Plan(goal_id=goal.id, status="ready")
        db.add(plan)
        await db.flush()
        phase = Phase(plan_id=plan.id, seq=1, title="语法基础", days=7, focus="变量与作用域", deliverable="")
        db.add(phase)
        await db.flush()
        task = Task(
            phase_id=phase.id,
            day_offset=0,
            title="可变对象与浅拷贝陷阱实验",
            type="coding",
            duration_min=45,
            resource="",
            acceptance="能解释三种复制方式的区别",
            repo_paths=[],
        )
        db.add(task)
        await db.commit()
        return user.id, task.id


async def test_task_guide_generated_and_cached(client, monkeypatch):
    fake = GuideLlm()
    monkeypatch.setattr(task_service, "get_llm", lambda: fake)
    user_id, task_id = await _seed_task("guide@example.com")

    guide = await task_service.get_or_create_task_guide(task_id, user_id)
    assert len(guide["steps"]) == 3
    assert len(guide["concepts"]) == 2
    assert guide["code_examples"][0]["language"] == "python"
    assert guide["materials"][0]["url"] == "https://fastapi.tiangolo.com/"
    assert fake.calls == 1

    cached = await task_service.get_or_create_task_guide(task_id, user_id)
    assert cached["steps"] == guide["steps"]
    assert fake.calls == 1

    async with SessionLocal() as db:
        rows = (await db.scalars(select(TaskGuide).where(TaskGuide.task_id == task_id))).all()
    assert len(rows) == 1


async def test_task_guide_is_owner_scoped(client, monkeypatch):
    fake = GuideLlm()
    monkeypatch.setattr(task_service, "get_llm", lambda: fake)
    _user_id, task_id = await _seed_task("guide-owner@example.com")

    with pytest.raises(task_service.GuideError):
        await task_service.get_or_create_task_guide(task_id, "another-user")
