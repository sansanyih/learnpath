"""Plan generation (SSE) and persisted plan reads."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_current_user_optional
from app.core.config import get_settings
from app.db.database import get_db
from app.db.models import (
    Annotation,
    Attempt,
    Chapter,
    ChapterProgress,
    ChapterQuiz,
    ChapterQuizAttempt,
    ChatMessage,
    Goal,
    KnowledgePoint,
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
from app.schemas.auth import PlanIn
from app.schemas.plan import (
    KnowledgePointOut,
    PhaseOut,
    PlanDetailOut,
    PlanSummary,
    TaskOut,
)
from app.schemas.repo import ChapterSummary, RepoIn, RepoSourceOut
from app.services import plan_service, repo_service
from app.services.quota import enforce_quota
from app.services.rate_limit import check_guest_limit

router = APIRouter(prefix="/plans", tags=["plans"])


def _guest_key(request: Request) -> str:
    guest_id = request.headers.get("x-guest-id", "").strip()
    if guest_id:
        return f"guest:{guest_id}"
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


async def _owned_plan(db: AsyncSession, plan_id: str, user_id: str) -> Plan | None:
    return await db.scalar(
        select(Plan).join(Goal).where(Plan.id == plan_id, Goal.user_id == user_id)
    )


@router.post("/stream")
async def stream_plan(
    payload: PlanIn,
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    if user is None:
        settings = get_settings()
        allowed, _count = await check_guest_limit(db, _guest_key(request), settings.guest_daily_limit)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "GUEST_LIMIT_REACHED",
                    "message": f"游客每天最多生成 {settings.guest_daily_limit} 次，登录后可继续",
                },
            )
    else:
        await enforce_quota(db, user.id)

    return StreamingResponse(
        plan_service.stream_plan(payload, user.id if user else None),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("", response_model=list[PlanSummary])
async def list_plans(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlanSummary]:
    stmt = (
        select(Plan)
        .join(Goal)
        .where(Goal.user_id == user.id)
        .options(
            selectinload(Plan.goal),
            selectinload(Plan.phases).options(selectinload(Phase.tasks)),
        )
        .order_by(Plan.created_at.desc())
        .limit(50)
    )
    plans = (await db.scalars(stmt)).all()
    return [
        PlanSummary(
            id=plan.id,
            goal_title=plan.goal.title,
            status=plan.status,
            created_at=plan.created_at,
            phase_count=len(plan.phases),
            task_count=sum(len(phase.tasks) for phase in plan.phases),
        )
        for plan in plans
    ]


@router.get("/{plan_id}", response_model=PlanDetailOut)
async def get_plan(
    plan_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlanDetailOut:
    stmt = (
        select(Plan)
        .where(Plan.id == plan_id)
        .options(
            selectinload(Plan.goal),
            selectinload(Plan.phases).options(
                selectinload(Phase.knowledge_points),
                selectinload(Phase.tasks),
            ),
        )
    )
    plan = await db.scalar(stmt)
    if plan is None or plan.goal.user_id != user.id:
        raise HTTPException(
            status_code=404,
            detail={"code": "PLAN_NOT_FOUND", "message": "计划不存在"},
        )

    phases = [
        PhaseOut(
            id=phase.id,
            seq=phase.seq,
            title=phase.title,
            days=phase.days,
            focus=phase.focus,
            deliverable=phase.deliverable,
            status=phase.status,
            knowledge_points=[KnowledgePointOut.model_validate(kp) for kp in phase.knowledge_points],
            tasks=[TaskOut.model_validate(task) for task in phase.tasks],
        )
        for phase in plan.phases
    ]
    return PlanDetailOut(
        id=plan.id,
        goal_title=plan.goal.title,
        goal_raw=plan.goal.raw_input,
        daily_minutes=plan.goal.daily_minutes,
        level=plan.goal.level,
        deadline=plan.goal.deadline,
        status=plan.status,
        created_at=plan.created_at,
        phases=phases,
    )


@router.get("/{plan_id}/suggestions")
async def plan_suggestions(
    plan_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    plan = await _owned_plan(db, plan_id, user.id)
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "PLAN_NOT_FOUND", "message": "计划不存在"},
        )
    rows = (
        await db.scalars(
            select(PlanAdjustment)
            .where(
                PlanAdjustment.plan_id == plan_id,
                PlanAdjustment.status == "pending",
            )
            .order_by(PlanAdjustment.created_at.desc())
        )
    ).all()
    return {
        "items": [
            {
                "id": row.id,
                "phase_id": row.phase_id,
                "action": row.action,
                "message": (row.payload or {}).get("message", ""),
                "tasks": (row.payload or {}).get("tasks", []),
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }


@router.delete("/{plan_id}", status_code=204)
async def delete_plan(
    plan_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    plan = await _owned_plan(db, plan_id, user.id)
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "PLAN_NOT_FOUND", "message": "计划不存在"},
        )

    phase_ids = select(Phase.id).where(Phase.plan_id == plan_id)
    task_ids = select(Task.id).where(Task.phase_id.in_(phase_ids))
    kp_ids = select(KnowledgePoint.id).where(KnowledgePoint.phase_id.in_(phase_ids))
    chapter_ids = select(Chapter.id).where(Chapter.plan_id == plan_id)

    # 顺序：先删引用方，再删被引用方（SQLite 默认不强制 FK 级联）
    await db.execute(delete(TaskGuide).where(TaskGuide.task_id.in_(task_ids)))
    await db.execute(delete(Attempt).where(Attempt.phase_id.in_(phase_ids)))
    await db.execute(delete(Mastery).where(Mastery.kp_id.in_(kp_ids)))
    await db.execute(delete(ReviewItem).where(ReviewItem.kp_id.in_(kp_ids)))
    await db.execute(delete(ReviewStreak).where(ReviewStreak.kp_id.in_(kp_ids)))
    await db.execute(delete(Quiz).where(Quiz.phase_id.in_(phase_ids)))
    await db.execute(delete(PlanAdjustment).where(PlanAdjustment.plan_id == plan_id))
    await db.execute(delete(ChapterProgress).where(ChapterProgress.chapter_id.in_(chapter_ids)))
    await db.execute(delete(ChapterQuizAttempt).where(ChapterQuizAttempt.chapter_id.in_(chapter_ids)))
    await db.execute(delete(ChapterQuiz).where(ChapterQuiz.chapter_id.in_(chapter_ids)))
    await db.execute(
        delete(ChatMessage).where(
            ChatMessage.scope == "chapter", ChatMessage.context_id.in_(chapter_ids)
        )
    )
    await db.execute(
        delete(Annotation).where(
            Annotation.scope == "chapter", Annotation.context_id.in_(chapter_ids)
        )
    )
    await db.execute(
        delete(ChatMessage).where(ChatMessage.scope == "task", ChatMessage.context_id.in_(task_ids))
    )
    await db.execute(
        delete(Annotation).where(Annotation.scope == "task", Annotation.context_id.in_(task_ids))
    )
    await db.execute(delete(Task).where(Task.phase_id.in_(phase_ids)))
    await db.execute(delete(KnowledgePoint).where(KnowledgePoint.phase_id.in_(phase_ids)))
    await db.execute(delete(Chapter).where(Chapter.plan_id == plan_id))
    await db.execute(delete(RepoSource).where(RepoSource.plan_id == plan_id))
    await db.execute(delete(Phase).where(Phase.plan_id == plan_id))

    goal_id = plan.goal_id
    await db.execute(delete(Plan).where(Plan.id == plan_id))
    await db.execute(delete(Goal).where(Goal.id == goal_id))
    await db.commit()
    return Response(status_code=204)


@router.post("/{plan_id}/repos/stream")
async def ingest_repo(
    plan_id: str,
    payload: RepoIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    plan = await _owned_plan(db, plan_id, user.id)
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "PLAN_NOT_FOUND", "message": "计划不存在"},
        )
    await enforce_quota(db, user.id)
    return StreamingResponse(
        repo_service.stream_repo_ingest(plan_id, user.id, payload.url),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{plan_id}/repos", response_model=list[RepoSourceOut])
async def list_repos(
    plan_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RepoSourceOut]:
    plan = await _owned_plan(db, plan_id, user.id)
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "PLAN_NOT_FOUND", "message": "计划不存在"},
        )

    repos = (
        await db.scalars(
            select(RepoSource)
            .where(RepoSource.plan_id == plan_id)
            .options(selectinload(RepoSource.chapters))
            .order_by(RepoSource.created_at.desc())
        )
    ).all()

    return [
        RepoSourceOut(
            id=repo.id,
            repo_full_name=repo.repo_full_name,
            ref=repo.ref,
            status=repo.status,
            file_count=repo.file_count,
            chapters=[
                ChapterSummary(
                    id=chapter.id,
                    seq=chapter.seq,
                    title=chapter.title,
                    purpose=chapter.purpose,
                    files=chapter.files or [],
                    concepts=chapter.concepts or [],
                    status=chapter.status,
                    has_content=bool(chapter.content_md),
                )
                for chapter in repo.chapters
            ],
        )
        for repo in repos
    ]
