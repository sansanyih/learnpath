"""Anonymous guest limits (daily quota keyed by guest id or IP)."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GuestLimit


async def check_guest_limit(db: AsyncSession, key: str, limit: int) -> tuple[bool, int]:
    """Increment today's counter and report whether the request is allowed."""
    today = date.today()
    row = await db.scalar(
        select(GuestLimit).where(GuestLimit.key == key, GuestLimit.window_start == today)
    )
    if row is None:
        row = GuestLimit(key=key, window_start=today, count=1)
        db.add(row)
        await db.commit()
        return True, 1

    if row.count >= limit:
        return False, row.count

    row.count += 1
    await db.commit()
    return True, row.count
