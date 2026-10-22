"""Auth endpoints: register / login / logout / change password / export / delete."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.database import get_db
from app.db.models import (
    AccountDeletion,
    Annotation,
    Attempt,
    Chapter,
    Goal,
    KnowledgePoint,
    LoginAttempt,
    Mastery,
    Phase,
    Plan,
    RepoSource,
    ReviewItem,
    Task,
    User,
    utcnow,
)
from app.schemas.auth import ChangePasswordIn, LoginIn, RegisterIn, TokenOut, UserOut

auth_router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(tags=["me"])

MAX_FAILURES = 5
LOCK_MINUTES = 15


def _aware(value):
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _record_failure(db: AsyncSession, key: str) -> None:
    now = utcnow()
    row = await db.scalar(select(LoginAttempt).where(LoginAttempt.key == key))
    if row is None:
        row = LoginAttempt(key=key, failures=1, window_start=now)
        db.add(row)
    else:
        window_start = _aware(row.window_start)
        if window_start is None or now - window_start > timedelta(minutes=LOCK_MINUTES):
            row.failures = 0
            row.window_start = now
            row.locked_until = None
        row.failures += 1
        if row.failures >= MAX_FAILURES:
            row.locked_until = now + timedelta(minutes=LOCK_MINUTES)
    await db.commit()


async def _check_lock(db: AsyncSession, key: str) -> None:
    row = await db.scalar(select(LoginAttempt).where(LoginAttempt.key == key))
    if row is None:
        return
    locked_until = _aware(row.locked_until)
    if locked_until and locked_until > utcnow():
        seconds = max(1, int((locked_until - utcnow()).total_seconds()))
        raise HTTPException(
            status_code=429,
            detail={
                "code": "LOGIN_LOCKED",
                "message": f"失败次数过多，请 {seconds // 60 + 1} 分钟后再试",
            },
        )


async def _clear_failures(db: AsyncSession, key: str) -> None:
    row = await db.scalar(select(LoginAttempt).where(LoginAttempt.key == key))
    if row is not None:
        await db.delete(row)
        await db.commit()


@auth_router.post("/register", response_model=UserOut, status_code=201)
async def register(payload: RegisterIn, db: AsyncSession = Depends(get_db)) -> User:
    email = payload.email.lower()
    if await db.scalar(select(User).where(User.email == email)):
        raise HTTPException(
            status_code=409,
            detail={"code": "EMAIL_TAKEN", "message": "这个邮箱已经注册过了"},
        )

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    await db.flush()
    return user


@auth_router.post("/login", response_model=TokenOut)
async def login(
    payload: LoginIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenOut:
    key = f"{_client_ip(request)}:{payload.email.lower()}"
    await _check_lock(db, key)

    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        await _record_failure(db, key)
        raise HTTPException(
            status_code=401,
            detail={"code": "BAD_CREDENTIALS", "message": "邮箱或密码不正确"},
        )

    if not user.is_active:
        deletion = await db.scalar(select(AccountDeletion).where(AccountDeletion.user_id == user.id))
        deleted_at = _aware(deletion.deleted_at) if deletion else None
        if deleted_at and utcnow() - deleted_at <= timedelta(days=7):
            user.is_active = True
            await db.delete(deletion)
            await db.commit()
        else:
            raise HTTPException(
                status_code=403,
                detail={"code": "ACCOUNT_DISABLED", "message": "账号已被停用"},
            )

    await _clear_failures(db, key)
    user.last_login_at = utcnow()
    token = create_access_token(user.id, user.token_version, get_settings())
    return TokenOut(token=token, user=UserOut.model_validate(user))


@me_router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@me_router.get("/me/export")
async def export_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    goals = (await db.scalars(select(Goal).where(Goal.user_id == user.id))).all()
    plan_ids = select(Plan.id).join(Goal).where(Goal.user_id == user.id)
    plans = (await db.scalars(select(Plan).join(Goal).where(Goal.user_id == user.id))).all()
    phases = (await db.scalars(select(Phase).where(Phase.plan_id.in_(plan_ids)))).all()
    tasks = (await db.scalars(select(Task).where(Task.phase_id.in_(select(Phase.id).where(Phase.plan_id.in_(plan_ids)))))).all()
    mastery = (await db.scalars(select(Mastery).where(Mastery.user_id == user.id))).all()
    attempts = (await db.scalars(select(Attempt).where(Attempt.user_id == user.id))).all()
    annotations = (await db.scalars(select(Annotation).where(Annotation.user_id == user.id))).all()
    reviews = (await db.scalars(select(ReviewItem).where(ReviewItem.user_id == user.id))).all()
    repos = (await db.scalars(select(RepoSource).where(RepoSource.plan_id.in_(plan_ids)))).all()
    chapters = (await db.scalars(select(Chapter).where(Chapter.plan_id.in_(plan_ids)))).all()

    return {
        "user": UserOut.model_validate(user).model_dump(),
        "goals": [{"id": x.id, "title": x.title, "raw_input": x.raw_input, "daily_minutes": x.daily_minutes, "level": x.level} for x in goals],
        "plans": [{"id": x.id, "goal_id": x.goal_id, "status": x.status, "created_at": x.created_at.isoformat()} for x in plans],
        "phases": [{"id": x.id, "plan_id": x.plan_id, "seq": x.seq, "title": x.title, "days": x.days, "status": x.status} for x in phases],
        "tasks": [{"id": x.id, "phase_id": x.phase_id, "title": x.title, "status": x.status, "day_offset": x.day_offset} for x in tasks],
        "mastery": [{"kp_id": x.kp_id, "score": x.score, "status": x.status, "attempts": x.attempts} for x in mastery],
        "attempts": [{"quiz_id": x.quiz_id, "score": x.score, "created_at": x.created_at.isoformat()} for x in attempts],
        "annotations": [{"scope": x.scope, "context_id": x.context_id, "content": x.content} for x in annotations],
        "reviews": [{"kp_id": x.kp_id, "due_at": x.due_at.isoformat() if x.due_at else None, "interval_days": x.interval_days} for x in reviews],
        "repos": [{"id": x.id, "full_name": x.repo_full_name, "ref": x.ref} for x in repos],
        "chapters": [{"id": x.id, "repo_source_id": x.repo_source_id, "title": x.title, "seq": x.seq} for x in chapters],
    }


@me_router.delete("/me")
async def delete_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user.is_active = False
    user.token_version += 1
    exists = await db.scalar(select(AccountDeletion).where(AccountDeletion.user_id == user.id))
    if exists is None:
        db.add(AccountDeletion(user_id=user.id))
    await db.commit()
    return {"ok": True, "message": "账号已注销，7 天内用原密码登录可恢复"}


@auth_router.post("/logout")
async def logout(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user.token_version += 1
    await db.commit()
    return {"ok": True, "message": "已退出登录"}


@auth_router.post("/change-password")
async def change_password(
    payload: ChangePasswordIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(
            status_code=400,
            detail={"code": "BAD_OLD_PASSWORD", "message": "旧密码不正确"},
        )
    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1
    await db.commit()
    return {"ok": True, "message": "密码已更新，其他设备需要重新登录"}
