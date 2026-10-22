"""List users and plans in dev DB (audit before cleanup)."""

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.db.models import Goal, Plan, User  # noqa: E402


async def main() -> None:
    async with SessionLocal() as db:
        users = (await db.scalars(select(User).order_by(User.created_at))).all()
        for user in users:
            plans = await db.scalar(
                select(func.count()).select_from(Plan).join(Goal).where(Goal.user_id == user.id)
            )
            print(f"{user.email} id={user.id[:8]} plans={plans} active={user.is_active}")


if __name__ == "__main__":
    asyncio.run(main())
