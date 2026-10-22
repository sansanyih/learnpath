"""Delete the cached guide for the first FastAPI task (dev only)."""

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.db.models import Task, TaskGuide  # noqa: E402


async def main() -> None:
    async with SessionLocal() as db:
        task = await db.scalar(select(Task).where(Task.title.like("搭建最小 FastAPI%")))
        row = await db.scalar(select(TaskGuide).where(TaskGuide.task_id == task.id))
        if row is not None:
            await db.delete(row)
            await db.commit()
            print("deleted", row.id)
        else:
            print("no cached guide")


if __name__ == "__main__":
    asyncio.run(main())
