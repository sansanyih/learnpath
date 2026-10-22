"""Smoke test against the real LLM: generates one persisted plan and prints SSE events."""

import asyncio
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.database import SessionLocal, engine  # noqa: E402
from app.db.models import Base, User  # noqa: E402
from app.schemas.auth import PlanIn  # noqa: E402
from app.services.plan_service import stream_plan  # noqa: E402

GOAL = "三个月掌握 FastAPI 后端开发，能独立写一个带鉴权和数据库的小服务"


async def main() -> None:
    settings = get_settings()
    print(f"model={settings.llm_model} llm_enabled={settings.llm_enabled}")
    if not settings.llm_enabled:
        print("LLM_API_KEY 未配置，退出")
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == "smoke@example.com"))
        if user is None:
            user = User(email="smoke@example.com", password_hash="smoke-not-a-login", display_name="smoke")
            db.add(user)
            await db.commit()
            await db.refresh(user)
        user_id = user.id

    payload = PlanIn(goal=GOAL, daily_minutes=45, level="intermediate")
    plan_id = None

    async for frame in stream_plan(payload, user_id):
        event_line = next((line for line in frame.splitlines() if line.startswith("event:")), "")
        data_line = next((line for line in frame.splitlines() if line.startswith("data:")), "")
        event = event_line.replace("event:", "").strip()
        data = data_line.replace("data:", "").strip()
        print(f"[{event}] {data[:160]}")

        if event == "done":
            payload_data = json.loads(data)
            plan_id = payload_data.get("plan_id")
            print(f"\nplan_id={plan_id} usage={payload_data.get('usage')} cost=¥{payload_data.get('cost_est')}")
        if event == "error":
            print("生成失败")
            return

    if plan_id:
        async with SessionLocal() as db:
            from app.db.models import Phase, Plan

            plan = await db.get(Plan, plan_id)
            print(f"plan status={plan.status if plan else 'missing'}")
            phases = (await db.scalars(select(Phase).where(Phase.plan_id == plan_id))).all()
            print(f"persisted phases={len(phases)}")


if __name__ == "__main__":
    asyncio.run(main())
