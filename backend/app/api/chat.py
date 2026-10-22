"""Agent chat SSE endpoint, history and annotations."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.database import get_db
from app.db.models import Annotation, ChatMessage, User
from app.schemas.annotation import AnnotationIn
from app.schemas.chat import ChatIn
from app.services import agent_service
from app.services.quota import enforce_quota
from app.services.rate_limit import check_guest_limit

router = APIRouter(tags=["chat"])


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    settings = get_settings()
    allowed, _count = await check_guest_limit(db, f"agent:{user.id}", settings.agent_daily_limit)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "AGENT_LIMIT_REACHED",
                "message": f"今天最多追问 {settings.agent_daily_limit} 次，明天再来或先看章节讲解",
            },
        )
    await enforce_quota(db, user.id)

    return StreamingResponse(
        agent_service.stream_chat(
            payload.scope,
            payload.context_id,
            user.id,
            payload.question,
            [item.model_dump() for item in payload.history],
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/chat/history")
async def chat_history(
    scope: str = Query(pattern="^(chapter|task)$"),
    context_id: str = Query(min_length=1, max_length=64),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = (
        await db.scalars(
            select(ChatMessage)
            .where(
                ChatMessage.user_id == user.id,
                ChatMessage.scope == scope,
                ChatMessage.context_id == context_id,
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(40)
        )
    ).all()
    rows = list(reversed(rows))
    return {
        "items": [
            {
                "id": row.id,
                "role": row.role,
                "content": row.content,
                "sources": row.sources or [],
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }


@router.post("/annotations")
async def create_annotation(
    payload: AnnotationIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = Annotation(
        user_id=user.id,
        scope=payload.scope,
        context_id=payload.context_id,
        content=payload.content,
    )
    db.add(row)
    await db.commit()
    return {"id": row.id, "created_at": row.created_at.isoformat()}


@router.get("/notes")
async def list_notes(
    scope: str = Query(pattern="^(chapter|task)$"),
    context_id: str = Query(min_length=1, max_length=64),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await list_annotations(scope, context_id, user, db)


@router.post("/notes")
async def create_note(
    payload: AnnotationIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await create_annotation(payload, user, db)


@router.get("/annotations")
async def list_annotations(
    scope: str = Query(pattern="^(chapter|task)$"),
    context_id: str = Query(min_length=1, max_length=64),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rows = (
        await db.scalars(
            select(Annotation)
            .where(
                Annotation.user_id == user.id,
                Annotation.scope == scope,
                Annotation.context_id == context_id,
            )
            .order_by(desc(Annotation.created_at))
            .limit(20)
        )
    ).all()
    return {
        "items": [
            {"id": row.id, "content": row.content, "created_at": row.created_at.isoformat()}
            for row in rows
        ]
    }
