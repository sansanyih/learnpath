"""Chapter detail and content generation."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models import Chapter, ChapterProgress, Goal, Plan, RepoSource, User
from app.repo.github import GitHubClient, RepoError
from app.schemas.chapter_status import ChapterStatusIn
from app.schemas.quiz import AnswerIn
from app.schemas.repo import ChapterDetailOut
from app.services import chapter_quiz_service, repo_service
from app.services.chapter_quiz_service import ChapterQuizError
from app.services.quota import enforce_quota

router = APIRouter(prefix="/chapters", tags=["chapters"])


class ChapterQuizSubmit(BaseModel):
    chapter_id: str
    answers: list[AnswerIn] = Field(default_factory=list)


def _quiz_error(exc: ChapterQuizError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail={"code": exc.code, "message": exc.message})


async def _owned_chapter(db: AsyncSession, chapter_id: str, user_id: str) -> Chapter | None:
    chapter = await db.get(Chapter, chapter_id)
    if chapter is None:
        return None
    plan = await db.get(Plan, chapter.plan_id)
    if plan is None:
        return None
    goal = await db.get(Goal, plan.goal_id)
    if goal is None or goal.user_id != user_id:
        return None
    return chapter


@router.get("/{chapter_id}", response_model=ChapterDetailOut)
async def get_chapter(
    chapter_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChapterDetailOut:
    chapter = await _owned_chapter(db, chapter_id, user.id)
    if chapter is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "CHAPTER_NOT_FOUND", "message": "章节不存在"},
        )
    return ChapterDetailOut(
        id=chapter.id,
        plan_id=chapter.plan_id,
        repo_id=chapter.repo_source_id,
        seq=chapter.seq,
        title=chapter.title,
        purpose=chapter.purpose,
        files=chapter.files or [],
        concepts=chapter.concepts or [],
        status=chapter.status,
        content_md=chapter.content_md,
    )


@router.post("/{chapter_id}/content")
async def generate_content(
    chapter_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await enforce_quota(db, user.id)
    try:
        return await repo_service.generate_chapter_content(chapter_id, user.id)
    except RepoError as exc:
        status = 404 if exc.code == "CHAPTER_NOT_FOUND" else 502
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": exc.message}) from exc


@router.get("/{chapter_id}/files")
async def get_chapter_files(
    chapter_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    chapter = await _owned_chapter(db, chapter_id, user.id)
    if chapter is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "CHAPTER_NOT_FOUND", "message": "章节不存在"},
        )

    repo = await db.get(RepoSource, chapter.repo_source_id)
    if repo is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "REPO_NOT_FOUND", "message": "仓库不存在"},
        )

    owner, repo_name = repo.repo_full_name.split("/", 1)
    files: list[dict] = []
    async with GitHubClient() as gh:
        semaphore = asyncio.Semaphore(6)

        async def fetch(path: str):
            async with semaphore:
                try:
                    return {"path": path, "content": (await gh.content(owner, repo_name, path, repo.ref))[:20000]}
                except RepoError:
                    return None

        results = await asyncio.gather(*(fetch(path) for path in (chapter.files or [])[:6]))
        files = [item for item in results if item is not None]
    return {"files": files}


@router.get("/{chapter_id}/progress")
async def get_chapter_progress(
    chapter_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    chapter = await _owned_chapter(db, chapter_id, user.id)
    if chapter is None:
        raise HTTPException(404, detail={"code": "CHAPTER_NOT_FOUND", "message": "章节不存在"})
    row = await db.scalar(
        select(ChapterProgress).where(
            ChapterProgress.user_id == user.id, ChapterProgress.chapter_id == chapter_id
        )
    )
    return {"status": row.status if row is not None else "todo"}


@router.put("/{chapter_id}/progress")
async def set_chapter_progress(
    chapter_id: str,
    payload: ChapterStatusIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    chapter = await _owned_chapter(db, chapter_id, user.id)
    if chapter is None:
        raise HTTPException(404, detail={"code": "CHAPTER_NOT_FOUND", "message": "章节不存在"})
    row = await db.scalar(
        select(ChapterProgress).where(
            ChapterProgress.user_id == user.id, ChapterProgress.chapter_id == chapter_id
        )
    )
    if row is None:
        row = ChapterProgress(user_id=user.id, chapter_id=chapter_id, status=payload.status)
        db.add(row)
    else:
        row.status = payload.status
    await db.commit()
    return {"status": payload.status}


@router.post("/{chapter_id}/quiz")
async def create_chapter_quiz(
    chapter_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await enforce_quota(db, user.id)
    try:
        return await chapter_quiz_service.get_or_create_chapter_quiz(chapter_id, user.id)
    except ChapterQuizError as exc:
        raise _quiz_error(exc) from exc


@router.post("/chapter-quiz/submit")
async def submit_chapter_quiz(
    payload: ChapterQuizSubmit,
    user: User = Depends(get_current_user),
) -> dict:
    try:
        return await chapter_quiz_service.submit_chapter_quiz(
            payload.chapter_id,
            user.id,
            [item.model_dump() for item in payload.answers],
        )
    except ChapterQuizError as exc:
        raise _quiz_error(exc) from exc


@router.get("/{chapter_id}/quiz/latest")
async def latest_chapter_quiz(
    chapter_id: str,
    user: User = Depends(get_current_user),
) -> dict:
    try:
        return await chapter_quiz_service.latest_chapter_attempt(chapter_id, user.id)
    except ChapterQuizError as exc:
        raise _quiz_error(exc) from exc
