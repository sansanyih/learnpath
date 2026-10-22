"""Dev helper: mint a JWT for the smoke user and point at its latest plan."""

import asyncio
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.db.models import Goal, Plan, User  # noqa: E402


async def main() -> None:
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == "smoke@example.com"))
        if user is None:
            print("{}")
            return
        plan = await db.scalar(
            select(Plan)
            .join(Goal)
            .where(Goal.user_id == user.id)
            .order_by(Plan.created_at.desc())
        )
        token = create_access_token(user.id, user.token_version, get_settings())
        payload = json.dumps({"token": token, "plan_id": plan.id if plan else None})
        if len(sys.argv) > 1:
            Path(sys.argv[1]).write_text(payload, encoding="utf-8")
        else:
            print(payload)


if __name__ == "__main__":
    asyncio.run(main())
