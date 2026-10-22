"""Verify the persisted structure of a generated plan."""

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.db.models import KnowledgePoint, LlmUsage, Phase, Plan, Task  # noqa: E402

PLAN_ID = "7b9a425d-031e-4dd9-bd16-5f9ee8891c5e"


async def main() -> None:
    async with SessionLocal() as db:
        plan = await db.get(Plan, PLAN_ID)
        if plan is None:
            print("plan missing")
            return
        phases = (await db.scalars(select(Phase).where(Phase.plan_id == PLAN_ID).order_by(Phase.seq))).all()
        task_count = 0
        for phase in phases:
            tasks = (await db.scalars(select(Task).where(Task.phase_id == phase.id))).all()
            kps = (await db.scalars(select(KnowledgePoint).where(KnowledgePoint.phase_id == phase.id))).all()
            task_count += len(tasks)
            print(f"seq={phase.seq} title={phase.title} days={phase.days} kps={len(kps)} tasks={len(tasks)}")
        usage = (await db.scalars(select(LlmUsage))).all()
        print(f"status={plan.status} phases={len(phases)} tasks={task_count} usage_rows={len(usage)}")


if __name__ == "__main__":
    asyncio.run(main())
