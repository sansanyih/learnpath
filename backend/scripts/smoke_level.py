"""Verify beginner plans start from fundamentals (real LLM)."""

import asyncio
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.db.models import User  # noqa: E402
from app.schemas.auth import PlanIn  # noqa: E402
from app.services.plan_service import stream_plan  # noqa: E402

OUT = Path(r"C:\Users\simple\AppData\Local\Temp\ui-ref\level-plan.json")


async def main() -> None:
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == "leveltest@example.com"))
        if user is None:
            user = User(email="leveltest@example.com", password_hash="x", display_name="leveltest")
            db.add(user)
            await db.commit()
            await db.refresh(user)
        user_id = user.id

    payload = PlanIn(goal="三个月掌握python", daily_minutes=45, level="beginner")
    phases = []
    plan_id = None
    async for frame in stream_plan(payload, user_id):
        lines = frame.splitlines()
        event = next((line[6:].strip() for line in lines if line.startswith("event:")), "")
        data = next((line[5:].strip() for line in lines if line.startswith("data:")), "")
        if event == "phase_skeleton":
            phases.append(json.loads(data))
        if event == "done":
            plan_id = json.loads(data).get("plan_id")
            break
        if event == "error":
            print("error", data)
            return

    OUT.write_text(json.dumps({"plan_id": plan_id, "phases": phases}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {OUT} phases={len(phases)}")


if __name__ == "__main__":
    asyncio.run(main())
