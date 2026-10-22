"""Learning stats: streak heatmap, weekly investment, review strategy."""

from datetime import timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models import Attempt, ChapterQuizAttempt, Goal, Phase, Plan, Task, User, utcnow

router = APIRouter(tags=["stats"])


def _aware(value):
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


@router.get("/stats")
async def learning_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    today = utcnow().date()
    start = today - timedelta(days=89)

    task_rows = (
        await db.execute(
            select(Task.completed_at, Task.duration_min)
            .join(Phase, Task.phase_id == Phase.id)
            .join(Plan, Phase.plan_id == Plan.id)
            .join(Goal, Plan.goal_id == Goal.id)
            .where(Goal.user_id == user.id, Task.completed_at.is_not(None))
        )
    ).all()
    attempt_rows = (
        await db.scalars(
            select(Attempt.created_at).where(
                Attempt.user_id == user.id, Attempt.created_at >= start
            )
        )
    ).all()
    chapter_attempts = (
        await db.scalars(
            select(ChapterQuizAttempt.created_at).where(
                ChapterQuizAttempt.user_id == user.id,
                ChapterQuizAttempt.created_at >= start,
            )
        )
    ).all()

    daily: dict = {
        start + timedelta(days=index): {"minutes": 0, "count": 0} for index in range(90)
    }
    for completed_at, minutes in task_rows:
        moment = _aware(completed_at)
        if moment and moment.date() in daily:
            daily[moment.date()]["minutes"] += int(minutes or 0)
            daily[moment.date()]["count"] += 1
    for created_at in [*attempt_rows, *chapter_attempts]:
        moment = _aware(created_at)
        if moment and moment.date() in daily:
            daily[moment.date()]["count"] += 1

    days = [
        {
            "date": day.isoformat(),
            "minutes": value["minutes"],
            "count": value["count"],
        }
        for day, value in daily.items()
    ]

    streak = 0
    cursor = today
    if daily[cursor]["count"] == 0:
        cursor -= timedelta(days=1)
    while cursor in daily and daily[cursor]["count"] > 0:
        streak += 1
        cursor -= timedelta(days=1)

    week_start = today - timedelta(days=today.weekday())
    week_days = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        week_days.append(
            {
                "date": day.isoformat(),
                "minutes": daily.get(day, {}).get("minutes", 0),
                "is_future": day > today,
            }
        )
    week_minutes = sum(item["minutes"] for item in week_days)

    daily_minutes = await db.scalar(
        select(Goal.daily_minutes)
        .join(Plan, Plan.goal_id == Goal.id)
        .where(Goal.user_id == user.id)
        .order_by(Plan.created_at.desc())
        .limit(1)
    )
    target = int(daily_minutes or 45) * 7

    return {
        "streak": streak,
        "days": days,
        "week": {
            "minutes": week_minutes,
            "target": target,
            "days": week_days,
        },
        "review_strategy": {"intervals": [1, 3, 7, 15, 30], "mastered_streak": 3},
    }
