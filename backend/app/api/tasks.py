"""Task completion toggle (feeds phase status and plan progress)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models import Goal, Phase, Plan, Task, TaskGuide, User, utcnow
from app.schemas.plan import TaskStatusIn
from app.services import task_service
from app.services.quota import enforce_quota
from app.services.task_service import GuideError

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.patch("/{task_id}")
async def update_task_status(
    task_id: str,
    payload: TaskStatusIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, detail={"code": "TASK_NOT_FOUND", "message": "任务不存在"})

    phase = await db.get(Phase, task.phase_id)
    plan = await db.get(Plan, phase.plan_id) if phase else None
    goal = await db.get(Goal, plan.goal_id) if plan else None
    if phase is None or plan is None or goal is None or goal.user_id != user.id:
        raise HTTPException(404, detail={"code": "TASK_NOT_FOUND", "message": "任务不存在"})

    task.status = payload.status
    task.completed_at = utcnow() if payload.status == "done" else None
    await db.flush()

    tasks = (await db.scalars(select(Task).where(Task.phase_id == phase.id))).all()
    done_count = sum(1 for item in tasks if item.status == "done")
    if done_count == 0:
        phase.status = "todo"
    elif done_count == len(tasks):
        phase.status = "done"
    else:
        phase.status = "doing"

    await db.commit()
    return {
        "id": task.id,
        "status": task.status,
        "phase_id": phase.id,
        "phase_status": phase.status,
    }


@router.get("/{task_id}")
async def get_task_detail(
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, detail={"code": "TASK_NOT_FOUND", "message": "任务不存在"})

    phase = await db.get(Phase, task.phase_id)
    plan = await db.get(Plan, phase.plan_id) if phase else None
    goal = await db.get(Goal, plan.goal_id) if plan else None
    if phase is None or plan is None or goal is None or goal.user_id != user.id:
        raise HTTPException(404, detail={"code": "TASK_NOT_FOUND", "message": "任务不存在"})

    siblings = (
        await db.scalars(
            select(Task).where(Task.phase_id == phase.id).order_by(Task.day_offset, Task.title)
        )
    ).all()
    guide = await db.scalar(select(TaskGuide).where(TaskGuide.task_id == task_id))
    guide_payload = None
    if (
        guide is not None
        and guide.payload
        and "concepts" in guide.payload
        and "code_examples" in guide.payload
    ):
        guide_payload = guide.payload

    return {
        "id": task.id,
        "title": task.title,
        "type": task.type,
        "duration_min": task.duration_min,
        "acceptance": task.acceptance,
        "status": task.status,
        "day_offset": task.day_offset,
        "phase_id": phase.id,
        "phase_title": phase.title,
        "plan_id": plan.id,
        "goal_title": goal.title,
        "phase_tasks": [
            {"id": item.id, "title": item.title, "status": item.status, "day_offset": item.day_offset}
            for item in siblings
        ],
        "guide": guide_payload,
    }


@router.post("/{task_id}/guide")
async def get_task_guide(
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await enforce_quota(db, user.id)
    try:
        return await task_service.get_or_create_task_guide(task_id, user.id)
    except GuideError as exc:
        raise HTTPException(
            status_code=exc.status,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
