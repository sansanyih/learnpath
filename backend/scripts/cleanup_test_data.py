"""Delete test users (@example.com) and their data; keep real accounts.

Usage: python scripts/cleanup_test_data.py [--apply]
"""

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select  # noqa: E402

from app.db.database import SessionLocal  # noqa: E402
from app.db.models import (  # noqa: E402
    AccountDeletion,
    Annotation,
    Attempt,
    Chapter,
    ChapterProgress,
    ChapterQuiz,
    ChapterQuizAttempt,
    ChatMessage,
    Goal,
    GuestLimit,
    KnowledgePoint,
    LlmUsage,
    LoginAttempt,
    Mastery,
    Phase,
    Plan,
    PlanAdjustment,
    Quiz,
    RepoSource,
    ReviewItem,
    ReviewStreak,
    Task,
    TaskGuide,
    User,
)

TEST_SUFFIX = "@example.com"


async def main() -> None:
    apply = "--apply" in sys.argv
    async with SessionLocal() as db:
        users = (await db.scalars(select(User).where(User.email.like(f"%{TEST_SUFFIX}")))).all()
        print(f"test users: {[u.email for u in users]}")
        if not users:
            print("nothing to clean")
            return

        for user in users:
            goals = (await db.scalars(select(Goal).where(Goal.user_id == user.id))).all()
            plan_ids = [g.id for g in goals]
            plans = (
                await db.scalars(select(Plan).where(Plan.goal_id.in_(plan_ids)))
            ).all() if plan_ids else []
            plan_id_values = [p.id for p in plans]
            phase_ids = (
                await db.scalars(select(Phase.id).where(Phase.plan_id.in_(plan_id_values)))
            ).all() if plan_id_values else []
            task_ids = (
                await db.scalars(select(Task.id).where(Task.phase_id.in_(phase_ids)))
            ).all() if phase_ids else []
            kp_ids = (
                await db.scalars(select(KnowledgePoint.id).where(KnowledgePoint.phase_id.in_(phase_ids)))
            ).all() if phase_ids else []
            chapter_ids = (
                await db.scalars(select(Chapter.id).where(Chapter.plan_id.in_(plan_id_values)))
            ).all() if plan_id_values else []

            await db.execute(delete(TaskGuide).where(TaskGuide.user_id == user.id))
            await db.execute(delete(Attempt).where(Attempt.user_id == user.id))
            await db.execute(delete(Quiz).where(Quiz.phase_id.in_(phase_ids)))
            await db.execute(delete(Mastery).where(Mastery.user_id == user.id))
            await db.execute(delete(ReviewItem).where(ReviewItem.user_id == user.id))
            await db.execute(delete(ReviewStreak).where(ReviewStreak.user_id == user.id))
            await db.execute(delete(PlanAdjustment).where(PlanAdjustment.user_id == user.id))
            await db.execute(delete(ChapterProgress).where(ChapterProgress.user_id == user.id))
            await db.execute(delete(ChapterQuizAttempt).where(ChapterQuizAttempt.user_id == user.id))
            await db.execute(delete(ChapterQuiz).where(ChapterQuiz.chapter_id.in_(chapter_ids)))
            await db.execute(delete(ChatMessage).where(ChatMessage.user_id == user.id))
            await db.execute(delete(Annotation).where(Annotation.user_id == user.id))
            await db.execute(delete(Task).where(Task.phase_id.in_(phase_ids)))
            await db.execute(delete(KnowledgePoint).where(KnowledgePoint.phase_id.in_(phase_ids)))
            await db.execute(delete(Chapter).where(Chapter.plan_id.in_(plan_id_values)))
            await db.execute(delete(RepoSource).where(RepoSource.plan_id.in_(plan_id_values)))
            await db.execute(delete(Phase).where(Phase.plan_id.in_(plan_id_values)))
            await db.execute(delete(Plan).where(Plan.id.in_(plan_id_values)))
            await db.execute(delete(Goal).where(Goal.id.in_(plan_ids)))
            await db.execute(delete(AccountDeletion).where(AccountDeletion.user_id == user.id))
            await db.execute(delete(LlmUsage).where(LlmUsage.user_id == user.id))
            await db.execute(delete(LoginAttempt).where(LoginAttempt.key.like(f"%{user.email}%")))
            await db.execute(delete(GuestLimit).where(GuestLimit.key == f"agent:{user.id}"))
            await db.delete(user)
            print(f"cleaned {user.email}: plans={len(plans)} phases={len(phase_ids)} tasks={len(task_ids)} kps={len(kp_ids)}")

        if apply:
            await db.execute(delete(GuestLimit))
            await db.commit()
            print("applied; guest limits cleared")
        else:
            await db.rollback()
            print("dry-run only; add --apply to commit")


if __name__ == "__main__":
    asyncio.run(main())
