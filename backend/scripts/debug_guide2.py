"""Probe the exact task whose guide fell back."""

import asyncio
import json
import sys
from pathlib import Path
from string import Template

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.db.models import Goal, Phase, Plan, Task  # noqa: E402
from app.llm.client import get_llm  # noqa: E402
from app.llm.guide_schemas import TaskGuideOut  # noqa: E402
from app.llm.prompts import load_prompt  # noqa: E402


async def main() -> None:
    async with SessionLocal() as db:
        task = await db.scalar(select(Task).where(Task.title.like("搭建最小 FastAPI%")))
        phase = await db.get(Phase, task.phase_id)
        plan = await db.get(Plan, phase.plan_id)
        goal = await db.get(Goal, plan.goal_id)

    system, template = load_prompt("task_guide_v1.txt")
    user = Template(template).substitute(
        goal=goal.title,
        phase=phase.title,
        focus=phase.focus,
        title=task.title,
        type=task.type,
        minutes=task.duration_min,
        acceptance=task.acceptance,
        level=goal.level,
    )
    result = await get_llm().chat_json(system, user, temperature=0.4, max_tokens=1800)
    print("RAW LEN:", len(result.text))
    data = json.loads(result.text)
    print("KEYS:", {key: len(value) if isinstance(value, list) else value for key, value in data.items()})
    try:
        out = TaskGuideOut.model_validate(data)
        print("VALID steps:", len(out.steps), "materials:", len(out.materials))
    except Exception as exc:
        print("INVALID:", exc)


if __name__ == "__main__":
    asyncio.run(main())
