"""Audit plan/phase task coverage against days and daily minutes."""

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.db.models import Goal, Phase, Plan, Task  # noqa: E402


async def main() -> None:
    async with SessionLocal() as db:
        plans = (
            await db.scalars(
                select(Plan)
                .options(selectinload(Plan.goal), selectinload(Plan.phases))
                .order_by(Plan.created_at.desc())
                .limit(10)
            )
        ).all()
        for plan in plans:
            phases = (
                await db.scalars(
                    select(Phase).where(Phase.plan_id == plan.id).order_by(Phase.seq)
                )
            ).all()
            total_days = sum(p.days for p in phases)
            total_tasks = 0
            problems = []
            for phase in phases:
                tasks = (
                    await db.scalars(select(Task).where(Task.phase_id == phase.id))
                ).all()
                total_tasks += len(tasks)
                offsets = sorted({t.day_offset for t in tasks})
                missing = [day for day in range(phase.days) if day not in offsets]
                minutes = sum(t.duration_min for t in tasks)
                capacity = phase.days * (plan.goal.daily_minutes if plan.goal else 45)
                if len(tasks) != phase.days or missing:
                    problems.append(
                        f"phase{phase.seq} days={phase.days} tasks={len(tasks)} "
                        f"unique_offsets={len(offsets)} missing={len(missing)} "
                        f"minutes={minutes}/{capacity}"
                    )
            print(
                f"plan {plan.id[:8]} goal={plan.goal.title[:24] if plan.goal else ''} "
                f"days={total_days} tasks={total_tasks}"
            )
            for line in problems[:8]:
                print("   ", line)


if __name__ == "__main__":
    asyncio.run(main())
