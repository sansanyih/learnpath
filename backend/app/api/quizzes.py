"""Phase quiz, grading and plan adjustment endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.schemas.quiz import PhaseQuizOut, SubmitIn, SubmitOut
from app.services import quiz_service
from app.services.quota import enforce_quota
from app.services.quiz_service import QuizError

router = APIRouter(tags=["quiz"])


def _http_error(exc: QuizError) -> HTTPException:
    return HTTPException(
        status_code=exc.status,
        detail={"code": exc.code, "message": exc.message},
    )


@router.post("/plans/{plan_id}/phases/{phase_id}/quiz", response_model=PhaseQuizOut)
async def create_phase_quiz(
    plan_id: str,
    phase_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PhaseQuizOut:
    await enforce_quota(db, user.id)
    try:
        return PhaseQuizOut(**(await quiz_service.get_or_create_phase_quiz(plan_id, phase_id, user.id)))
    except QuizError as exc:
        raise _http_error(exc) from exc


@router.post("/quizzes/submit", response_model=SubmitOut)
async def submit_quiz(
    payload: SubmitIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubmitOut:
    await enforce_quota(db, user.id)
    try:
        data = await quiz_service.submit_phase_quiz(
            payload.phase_id,
            user.id,
            [item.model_dump() for item in payload.answers],
        )
        return SubmitOut(**data)
    except QuizError as exc:
        raise _http_error(exc) from exc


@router.post("/adjustments/{adjustment_id}/adopt")
async def adopt_adjustment(
    adjustment_id: str,
    user: User = Depends(get_current_user),
) -> dict:
    try:
        return await quiz_service.adopt_adjustment(adjustment_id, user.id)
    except QuizError as exc:
        raise _http_error(exc) from exc


@router.post("/adjustments/{adjustment_id}/ignore")
async def ignore_adjustment(
    adjustment_id: str,
    user: User = Depends(get_current_user),
) -> dict:
    try:
        return await quiz_service.ignore_adjustment(adjustment_id, user.id)
    except QuizError as exc:
        raise _http_error(exc) from exc
