"""Adopt the latest pending adjustment for the smoke user (dev verification)."""

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.db.models import PlanAdjustment, User  # noqa: E402
from app.services import quiz_service  # noqa: E402


async def main() -> None:
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == "smoke@example.com"))
        row = await db.scalar(
            select(PlanAdjustment)
            .where(PlanAdjustment.user_id == user.id, PlanAdjustment.status == "pending")
            .order_by(PlanAdjustment.created_at.desc())
        )
        if row is None:
            print("no pending adjustment")
            return
        print(f"adopting {row.id} action={row.action}")
        result = await quiz_service.adopt_adjustment(row.id, user.id)
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
