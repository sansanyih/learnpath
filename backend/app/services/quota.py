"""Per-user daily token quota (based on llm_usage)."""

from datetime import datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException

from app.core.config import get_settings
from app.db.models import LlmUsage


async def usage_today(db: AsyncSession, user_id: str) -> int:
    start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
    total = await db.scalar(
        select(
            func.coalesce(func.sum(LlmUsage.tokens_in + LlmUsage.tokens_out), 0)
        ).where(LlmUsage.user_id == user_id, LlmUsage.created_at >= start)
    )
    return int(total or 0)


async def has_token_quota(db: AsyncSession, user_id: str, limit: int) -> tuple[bool, int]:
    used = await usage_today(db, user_id)
    return used < limit, used


async def enforce_quota(db: AsyncSession, user_id: str) -> None:
    limit = get_settings().user_daily_token_limit
    allowed, used = await has_token_quota(db, user_id, limit)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "USER_QUOTA_EXCEEDED",
                "message": f"今天已用 {used} tokens，达到每日上限 {limit}，明天再继续或降低生成频率",
            },
        )
