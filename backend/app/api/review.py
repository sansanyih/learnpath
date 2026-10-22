"""Review queue and mastery dashboard (rule-based SM-2 lite)."""

from datetime import timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models import (
    Goal,
    KnowledgePoint,
    Mastery,
    Phase,
    Plan,
    ReviewItem,
    ReviewStreak,
    User,
    utcnow,
)

router = APIRouter(tags=["review"])

INTERVALS = [1, 3, 7, 15, 30]


def _as_aware(value):
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class ReviewResultIn(BaseModel):
    result: Literal["again", "hard", "good"]


def _owned(db: AsyncSession, user_id: str, kp_id: str):
    return (
        select(Phase, Plan, Goal)
        .join(KnowledgePoint, KnowledgePoint.phase_id == Phase.id)
        .join(Plan, Phase.plan_id == Plan.id)
        .join(Goal, Plan.goal_id == Goal.id)
        .where(KnowledgePoint.id == kp_id, Goal.user_id == user_id)
    )


@router.get("/review/queue")
async def review_queue(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = (
        await db.execute(
            select(ReviewItem, KnowledgePoint, Phase, Plan)
            .join(KnowledgePoint, ReviewItem.kp_id == KnowledgePoint.id)
            .join(Phase, KnowledgePoint.phase_id == Phase.id)
            .join(Plan, Phase.plan_id == Plan.id)
            .join(Goal, Plan.goal_id == Goal.id)
            .where(Goal.user_id == user.id)
            .order_by(ReviewItem.due_at.asc())
            .limit(50)
        )
    ).all()

    mastery_map = {
        item.kp_id: item
        for item in (await db.scalars(select(Mastery).where(Mastery.user_id == user.id))).all()
    }
    now = utcnow()
    soon = now + timedelta(hours=24)
    items = []
    for item, kp, phase, plan in rows:
        mastery = mastery_map.get(kp.id)
        due_at = _as_aware(item.due_at)
        if due_at is not None and due_at > soon:
            continue
        items.append(
            {
                "id": item.id,
                "kp_id": kp.id,
                "kp_name": kp.name,
                "objective": kp.objective,
                "phase_title": phase.title,
                "plan_id": plan.id,
                "due_at": due_at.isoformat() if due_at else None,
                "overdue": bool(due_at and due_at <= now),
                "interval_days": item.interval_days,
                "mastery_score": round((mastery.score if mastery else 0) * 100),
                "mastery_status": mastery.status if mastery else "new",
            }
        )
    return {"items": items, "total": len(items)}


@router.post("/review/{review_id}/complete")
async def complete_review(
    review_id: str,
    payload: ReviewResultIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    item = await db.get(ReviewItem, review_id)
    if item is None:
        raise HTTPException(404, detail={"code": "REVIEW_NOT_FOUND", "message": "复习项不存在"})

    owned = await db.scalar(_owned(db, user.id, item.kp_id))
    if owned is None:
        raise HTTPException(404, detail={"code": "REVIEW_NOT_FOUND", "message": "复习项不存在"})

    interval = item.interval_days or 1
    ease = item.ease or 2.5
    streak_row = await db.scalar(
        select(ReviewStreak).where(ReviewStreak.user_id == user.id, ReviewStreak.kp_id == item.kp_id)
    )
    if streak_row is None:
        streak_row = ReviewStreak(user_id=user.id, kp_id=item.kp_id, streak=0)
        db.add(streak_row)

    if payload.result == "again":
        interval = 1
        ease = max(1.3, ease - 0.2)
        streak_row.streak = 0
    elif payload.result == "hard":
        interval = item.interval_days or 3
        ease = max(1.3, ease - 0.1)
        streak_row.streak = 0
    else:
        streak_row.streak += 1
        current = item.interval_days or 0
        interval = next((value for value in INTERVALS if value > current), 30)
        if streak_row.streak >= 3:
            interval = 30
        ease = min(3.0, ease + 0.1)

    item.interval_days = interval
    item.ease = ease
    item.last_result = payload.result
    item.due_at = utcnow() + timedelta(days=interval)

    mastery = await db.scalar(
        select(Mastery).where(Mastery.user_id == user.id, Mastery.kp_id == item.kp_id)
    )
    if mastery is not None:
        mastery.due_at = item.due_at
        mastery.interval_days = interval
        mastery.ease = ease
        if payload.result == "good":
            mastery.score = min(1.0, (mastery.score or 0) + 0.08)
        elif payload.result == "hard":
            mastery.score = max(0.0, (mastery.score or 0) - 0.05)
        if streak_row.streak >= 3:
            mastery.status = "mastered"
            mastery.score = 1.0

    await db.commit()
    return {
        "ok": True,
        "interval_days": interval,
        "due_at": item.due_at.isoformat(),
        "streak": streak_row.streak,
        "mastered": streak_row.streak >= 3,
    }


@router.get("/reviews/due")
async def reviews_due(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await review_queue(user, db)


@router.post("/reviews/{review_id}/complete")
async def reviews_complete(
    review_id: str,
    payload: ReviewResultIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await complete_review(review_id, payload, user, db)


@router.get("/mastery")
async def mastery_dashboard(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = (
        await db.execute(
            select(Mastery, KnowledgePoint, Phase, Plan)
            .join(KnowledgePoint, Mastery.kp_id == KnowledgePoint.id)
            .join(Phase, KnowledgePoint.phase_id == Phase.id)
            .join(Plan, Phase.plan_id == Plan.id)
            .join(Goal, Plan.goal_id == Goal.id)
            .where(Goal.user_id == user.id)
            .order_by(Mastery.score.asc())
        )
    ).all()

    items = [
        {
            "kp_id": kp.id,
            "kp_name": kp.name,
            "phase_title": phase.title,
            "plan_id": plan.id,
            "score": round((mastery.score or 0) * 100),
            "status": mastery.status,
            "attempts": mastery.attempts,
            "last_score": mastery.last_score,
            "due_at": mastery.due_at.isoformat() if mastery.due_at else None,
        }
        for mastery, kp, phase, plan in rows
    ]
    counts = {"mastered": 0, "learning": 0, "review": 0}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    average = round(sum(item["score"] for item in items) / len(items)) if items else 0
    return {
        "items": items,
        "summary": {"average": average, "total": len(items), **counts},
    }
