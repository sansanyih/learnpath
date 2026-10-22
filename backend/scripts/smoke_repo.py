"""Smoke test for repo ingestion: GitHub -> profile -> chapters -> persistence."""

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.db.models import Chapter, Goal, Plan, User  # noqa: E402
from app.services.repo_service import stream_repo_ingest  # noqa: E402

URL = "https://github.com/bnufw/lear_by_ai"


async def main() -> None:
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == "smoke@example.com"))
        if user is None:
            print("smoke user missing, run smoke_plan first")
            return
        plan = await db.scalar(
            select(Plan).join(Goal).where(Goal.user_id == user.id).order_by(Plan.created_at.desc())
        )
        if plan is None:
            print("no plan for smoke user")
            return
        user_id, plan_id = user.id, plan.id

    repo_id = None
    async for frame in stream_repo_ingest(plan_id, user_id, URL):
        event_line = next((line for line in frame.splitlines() if line.startswith("event:")), "")
        data_line = next((line for line in frame.splitlines() if line.startswith("data:")), "")
        event = event_line.replace("event:", "").strip()
        data = data_line.replace("data:", "").strip()
        print(f"[{event}] {data[:180]}")
        if event == "done":
            repo_id = data

    if repo_id:
        async with SessionLocal() as db:
            chapters = (
                await db.scalars(
                    select(Chapter).where(Chapter.plan_id == plan_id).order_by(Chapter.seq)
                )
            ).all()
            print(f"persisted chapters={len(chapters)}")
            for chapter in chapters:
                print(f"  {chapter.seq}. {chapter.title} files={len(chapter.files or [])}")


if __name__ == "__main__":
    asyncio.run(main())
