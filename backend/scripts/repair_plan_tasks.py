"""Repair phase tasks so each phase has exactly one task per day.

Usage: python scripts/repair_plan_tasks.py [--apply]
"""

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


async def repair(apply: bool) -> None:
    inserted = deleted = trimmed = 0
    async with SessionLocal() as db:
        plans = (await db.scalars(select(Plan))).all()
        for plan in plans:
            goal = await db.get(Goal, plan.goal_id)
            daily = goal.daily_minutes if goal else 45
            phases = (
                await db.scalars(
                    select(Phase)
                .where(Phase.plan_id == plan.id)
                .options(selectinload(Phase.knowledge_points))
                .order_by(Phase.seq)
                )
            ).all()
            for phase in phases:
                tasks = (
                    await db.scalars(
                        select(Task)
                        .where(Task.phase_id == phase.id)
                        .order_by(Task.day_offset, Task.title)
                    )
                ).all()
                by_day: dict[int, Task] = {}
                for task in tasks:
                    if task.day_offset >= phase.days:
                        if task.status == "done":
                            task.day_offset = phase.days - 1
                        else:
                            if apply:
                                await db.delete(task)
                            deleted += 1
                            continue
                    existing = by_day.get(task.day_offset)
                    if existing is None or (task.status == "done" and existing.status != "done"):
                        if existing is not None and apply:
                            await db.delete(existing)
                            deleted += 1
                        by_day[task.day_offset] = task
                    else:
                        if apply:
                            await db.delete(task)
                        deleted += 1

                for day in range(phase.days):
                    if day in by_day:
                        continue
                    kp = phase.knowledge_points[0].name if phase.knowledge_points else phase.title
                    task = Task(
                        phase_id=phase.id,
                        day_offset=day,
                        title=f"第 {day + 1} 天补练：{phase.title} 复盘与自测",
                        type="review" if day % 2 == 0 else "quiz",
                        duration_min=min(daily, 45),
                        resource="章节讲解 / 官方文档",
                        acceptance="完成当天复盘，记录 1 个易错点并通过自测",
                        repo_paths=[],
                    )
                    db.add(task)
                    inserted += 1

                if apply and deleted:
                    await db.flush()

        if apply:
            await db.commit()
    print(f"apply={apply} inserted={inserted} deleted={deleted}")


async def main() -> None:
    await repair("--apply" in sys.argv)


if __name__ == "__main__":
    asyncio.run(main())
