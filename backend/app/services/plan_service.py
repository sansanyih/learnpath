"""Plan generation pipeline: skeleton -> validation -> persistence -> phase details."""

import asyncio
import json
import re
from datetime import date
from string import Template

from sqlalchemy import select

from app.core.config import get_settings
from app.core.sse import sse
from app.db.database import SessionLocal
from app.db.models import Goal, KnowledgePoint, LlmUsage, Phase, Plan, Task
from app.llm.client import LlmError, LlmResult, get_llm
from app.llm.json_call import call_json
from app.llm.prompts import load_prompt
from app.llm.schemas import PhaseDetailOut, PhaseSkeletonIn, SkeletonOut, TaskIn
from app.schemas.auth import PlanIn

FALLBACK_ASSUMPTION = "模型输出不合法，已使用通用骨架；建议重新生成或换个说法。"


def _parse_horizon_days(goal: str) -> int | None:
    """Infer the learning horizon from the goal text (三个月 / 6周 / 90天 / 半年)."""
    text = goal.strip()
    numerals = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    suffix = {"十一": 11, "十二": 12}

    def to_int(raw: str) -> int | None:
        if raw.isdigit():
            return int(raw)
        if raw in suffix:
            return suffix[raw]
        return numerals.get(raw)

    month_match = re.search(r"(\d+|[一二两三四五六七八九十]+)\s*个?\s*月", text)
    if month_match and to_int(month_match.group(1)):
        return max(7, to_int(month_match.group(1)) * 30)
    week_match = re.search(r"(\d+|[一二两三四五六七八九十]+)\s*周", text)
    if week_match and to_int(week_match.group(1)):
        return max(7, to_int(week_match.group(1)) * 7)
    day_match = re.search(r"(\d+)\s*天", text)
    if day_match:
        return max(7, int(day_match.group(1)))
    if "半年" in text:
        return 180
    if "一年" in text or "1年" in text:
        return 365
    return None


def _available_days(deadline: date | None, goal: str = "") -> int:
    if deadline is not None:
        return max(7, (deadline - date.today()).days)
    return _parse_horizon_days(goal) or 42


def _normalize_days(skeleton: SkeletonOut, available: int) -> SkeletonOut:
    """Scale phase days so the plan actually covers the requested horizon."""
    phases = skeleton.phases
    total = sum(phase.days for phase in phases)
    if total <= 0:
        return skeleton
    if abs(total - available) <= max(2, int(available * 0.12)):
        return skeleton

    factor = available / total
    for phase in phases:
        phase.days = max(1, round(phase.days * factor))

    diff = available - sum(phase.days for phase in phases)
    phases[-1].days = max(1, phases[-1].days + diff)
    return skeleton


def _validate_skeleton(skeleton: SkeletonOut, available_days: int) -> None:
    seen: list[str] = []
    for phase in skeleton.phases:
        if phase.id in seen:
            raise ValueError(f"阶段 id 重复：{phase.id}")
        for prerequisite in phase.prerequisites:
            if prerequisite not in seen:
                raise ValueError(f"阶段 {phase.id} 的前置 {prerequisite} 未在前面定义")
        seen.append(phase.id)

    total_days = sum(phase.days for phase in skeleton.phases)
    if total_days > available_days:
        raise ValueError(f"阶段总天数 {total_days} 超过可用天数 {available_days}")


def _validate_detail(detail: PhaseDetailOut, phase: PhaseSkeletonIn, daily_minutes: int) -> None:
    if len(detail.tasks) != phase.days:
        raise ValueError(f"任务数 {len(detail.tasks)} 与阶段天数 {phase.days} 不一致")
    offsets = sorted(task.day_offset for task in detail.tasks)
    if offsets != list(range(phase.days)):
        raise ValueError(f"day_offset 必须覆盖 0..{phase.days - 1} 且不重复")
    for task in detail.tasks:
        if task.duration_min > daily_minutes:
            raise ValueError(f"任务「{task.title}」时长 {task.duration_min} 超过每天 {daily_minutes} 分钟")


def _fallback_detail(phase: PhaseSkeletonIn, daily_minutes: int) -> PhaseDetailOut:
    action_by_type = {
        "reading": "读",
        "coding": "练",
        "quiz": "测",
        "review": "复盘",
        "writing": "写",
    }
    types = ["reading", "coding", "quiz", "review", "writing"]
    tasks: list[TaskIn] = []
    for day in range(phase.days):
        kp = phase.knowledge_points[day % len(phase.knowledge_points)]
        task_type = types[day % len(types)]
        action = action_by_type[task_type]
        duration = min(daily_minutes, 45 if task_type not in {"quiz", "review"} else 30)
        tasks.append(
            TaskIn(
                day_offset=day,
                title=f"{action}：第 {day + 1} 天 · {kp.name}",
                type=task_type,
                duration_min=max(5, duration),
                resource="官方文档 / 章节讲解",
                acceptance=f"围绕「{kp.name}」完成{action}，能用自己的话说明要点",
            )
        )
    return PhaseDetailOut(tasks=tasks)


def _fallback_skeleton(payload: PlanIn) -> SkeletonOut:
    available = _available_days(payload.deadline, payload.goal)
    days = max(3, available // 4)
    phases = [
        (
            "p1",
            "基础准备",
            days,
            "跑通最小示例，建立手感",
            [
                ("工具链", "能独立装好环境并跑通 hello world"),
                ("最小示例", "不看文档复现一次并解释每一步"),
                ("学习路径", "用自己的话说明这个领域的知识地图"),
            ],
            "一个可运行的最小示例",
        ),
        (
            "p2",
            "核心概念",
            days,
            "理解核心机制，能用自己的话复述",
            [
                ("核心模型", "画出机制流程并标注关键环节"),
                ("常见术语", "用一句话向新人解释三个术语"),
                ("典型场景", "说出两个适用场景与一个不适用场景"),
            ],
            "一份概念笔记",
        ),
        (
            "p3",
            "动手实践",
            days,
            "完成一个能演示的小项目",
            [
                ("需求拆解", "把需求拆成三个可验证的小任务"),
                ("调试与测试", "为关键路径写至少一个自动化测试"),
                ("代码组织", "说明模块划分与依赖方向"),
            ],
            "一个可演示的小项目",
        ),
        (
            "p4",
            "综合验收",
            days,
            "独立讲清楚并复盘",
            [
                ("方案取舍", "说出两个备选方案与选择理由"),
                ("复盘", "列出三个踩坑点与改进项"),
                ("表达", "用五分钟讲清整个项目"),
            ],
            "一份复盘文档",
        ),
    ]
    return SkeletonOut(
        phases=[
            PhaseSkeletonIn(
                id=pid,
                title=title,
                days=phase_days,
                focus=focus,
                prerequisites=[] if index == 0 else [phases[index - 1][0]],
                knowledge_points=[{"name": name, "objective": objective} for name, objective in kps],
                deliverable=deliverable,
            )
            for index, (pid, title, phase_days, focus, kps, deliverable) in enumerate(phases)
        ],
        assumptions=[FALLBACK_ASSUMPTION],
    )


async def _call_json(
    purpose: str,
    system: str,
    user: str,
    schema_cls,
    extra_validate,
    temperature: float,
    max_tokens: int,
) -> tuple[object, list[LlmResult]]:
    return await call_json(
        purpose=purpose,
        system=system,
        user=user,
        schema_cls=schema_cls,
        extra_validate=extra_validate,
        temperature=temperature,
        max_tokens=max_tokens,
        llm=get_llm(),
    )


def _record_usage(db, user_id: str | None, purpose: str, result: LlmResult) -> float:
    settings = get_settings()
    cost = (
        result.tokens_in / 1000 * settings.llm_price_in_per_1k
        + result.tokens_out / 1000 * settings.llm_price_out_per_1k
    )
    db.add(
        LlmUsage(
            user_id=user_id,
            purpose=purpose,
            model=settings.llm_model,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_est=round(cost, 6),
            latency_ms=result.latency_ms,
            ok=True,
        )
    )
    return cost


async def _generate_skeleton(payload: PlanIn) -> tuple[SkeletonOut, list[LlmResult]]:
    system, user_template = load_prompt("plan_skeleton_v1.txt")
    available = _available_days(payload.deadline, payload.goal)
    user = Template(user_template).substitute(
        goal=payload.goal,
        level=payload.level,
        daily_minutes=payload.daily_minutes,
        deadline=payload.deadline.isoformat() if payload.deadline else "未指定",
        today=date.today().isoformat(),
        available_days=available,
    )
    skeleton, usages = await _call_json(
        purpose="plan_skeleton",
        system=system,
        user=user,
        schema_cls=SkeletonOut,
        extra_validate=lambda obj: _validate_skeleton(obj, available),
        temperature=0.3,
        max_tokens=3000,
    )
    return _normalize_days(skeleton, available), usages


async def _generate_detail(
    phase: PhaseSkeletonIn, payload: PlanIn
) -> tuple[PhaseDetailOut, list[LlmResult]]:
    system, user_template = load_prompt("phase_detail_v1.txt")
    phase_json = json.dumps(
        {
            "id": phase.id,
            "title": phase.title,
            "days": phase.days,
            "focus": phase.focus,
            "knowledge_points": [kp.model_dump() for kp in phase.knowledge_points],
            "deliverable": phase.deliverable,
        },
        ensure_ascii=False,
    )
    user = Template(user_template).substitute(
        phase_json=phase_json,
        daily_minutes=payload.daily_minutes,
        level=payload.level,
        days=phase.days,
    )
    return await _call_json(
        purpose="plan_detail",
        system=system,
        user=user,
        schema_cls=PhaseDetailOut,
        extra_validate=lambda obj: _validate_detail(obj, phase, payload.daily_minutes),
        temperature=0.4,
        max_tokens=4000,
    )


async def stream_plan(payload: PlanIn, user_id: str | None):
    """Yield SSE frames for one plan. Guests get skeleton only; users get persistence + tasks."""
    llm = get_llm()
    if not llm.enabled:
        from app.services.mock_plan import stream_mock_plan

        async for event in stream_mock_plan(payload):
            yield event
        return

    db = SessionLocal() if user_id else None
    plan: Plan | None = None
    phase_rows: dict[str, Phase] = {}
    tokens_in = tokens_out = 0
    cost_total = 0.0

    try:
        if db is not None:
            goal = Goal(
                user_id=user_id,
                title=payload.goal[:120],
                raw_input=payload.goal,
                deadline=payload.deadline,
                daily_minutes=payload.daily_minutes,
                level=payload.level,
            )
            db.add(goal)
            await db.flush()
            plan = Plan(goal_id=goal.id, status="generating")
            db.add(plan)
            await db.flush()
            await db.commit()

        yield sse("meta", {"stage": "skeleton", "plan_id": plan.id if plan else None, "mock": False})

        try:
            skeleton, usages = await _generate_skeleton(payload)
        except LlmError as exc:
            yield sse("notice", {"message": "模型输出不稳定，已切换为通用骨架。"})
            skeleton = _fallback_skeleton(payload)
            usages = []

        for result in usages:
            tokens_in += result.tokens_in
            tokens_out += result.tokens_out
            if db is not None:
                cost_total += _record_usage(db, user_id, "plan_skeleton", result)

        if db is not None and plan is not None:
            for seq, phase in enumerate(skeleton.phases, start=1):
                row = Phase(
                    plan_id=plan.id,
                    seq=seq,
                    title=phase.title,
                    days=phase.days,
                    focus=phase.focus,
                    deliverable=phase.deliverable,
                    status="todo",
                    prerequisites=phase.prerequisites,
                )
                db.add(row)
                await db.flush()
                phase_rows[phase.id] = row
                for kp_seq, kp in enumerate(phase.knowledge_points, start=1):
                    db.add(
                        KnowledgePoint(
                            phase_id=row.id,
                            name=kp.name,
                            objective=kp.objective,
                            seq=kp_seq,
                        )
                    )
            plan.skeleton = skeleton.model_dump()
            await db.commit()

        for seq, phase in enumerate(skeleton.phases, start=1):
            yield sse(
                "phase_skeleton",
                {
                    "id": phase.id,
                    "seq": seq,
                    "title": phase.title,
                    "days": phase.days,
                    "focus": phase.focus,
                    "knowledge_points": [kp.model_dump() for kp in phase.knowledge_points],
                },
            )

        yield sse(
            "skeleton_done",
            {"phases": len(skeleton.phases), "assumptions": skeleton.assumptions},
        )

        if plan is None:
            yield sse(
                "done",
                {
                    "plan_id": None,
                    "mock": False,
                    "hint": "登录后可保存计划并生成每日任务",
                    "usage": {"in": tokens_in, "out": tokens_out},
                    "cost_est": round(cost_total, 4),
                },
            )
            return

        semaphore = asyncio.Semaphore(3)

        async def build(phase: PhaseSkeletonIn):
            async with semaphore:
                try:
                    detail, usages = await _generate_detail(phase, payload)
                    return phase, detail, usages, False
                except LlmError:
                    return phase, _fallback_detail(phase, payload.daily_minutes), [], True

        tasks = [asyncio.create_task(build(phase)) for phase in skeleton.phases]
        failures = 0
        fallback_phases = 0

        for future in asyncio.as_completed(tasks):
            try:
                phase, detail, usages, used_fallback = await future
            except Exception as exc:  # noqa: BLE001 - one phase should not kill the plan
                failures += 1
                yield sse(
                    "error",
                    {
                        "code": "PHASE_DETAIL_FAILED",
                        "message": f"某个阶段的每日任务生成失败：{str(exc)[:160]}",
                        "retryable": False,
                    },
                )
                continue

            if used_fallback:
                fallback_phases += 1
                yield sse(
                    "notice",
                    {"message": f"阶段「{phase.title}」任务生成失败，已使用兜底任务"},
                )

            for result in usages:
                tokens_in += result.tokens_in
                tokens_out += result.tokens_out
                cost_total += _record_usage(db, user_id, "plan_detail", result)

            row = phase_rows[phase.id]
            db.add_all(
                [
                    Task(
                        phase_id=row.id,
                        day_offset=task.day_offset,
                        title=task.title,
                        type=task.type,
                        duration_min=task.duration_min,
                        resource=task.resource,
                        acceptance=task.acceptance,
                        repo_paths=[],
                    )
                    for task in detail.tasks
                ]
            )
            await db.commit()
            yield sse(
                "phase_detail",
                {
                    "phase_id": row.id,
                    "seq": row.seq,
                    "tasks": [task.model_dump() for task in detail.tasks],
                },
            )

        plan.status = "ready"
        await db.commit()
        yield sse(
            "done",
            {
                "plan_id": plan.id,
                "mock": False,
                "failed_phases": failures,
                "fallback_phases": fallback_phases,
                "usage": {"in": tokens_in, "out": tokens_out},
                "cost_est": round(cost_total, 4),
            },
        )

    except LlmError as exc:
        if db is not None and plan is not None:
            plan.status = "failed"
            await db.commit()
        yield sse("error", {"code": exc.code, "message": exc.message, "retryable": exc.retryable})
    except Exception:  # noqa: BLE001 - keep the stream readable
        if db is not None and plan is not None:
            plan.status = "failed"
            await db.commit()
        yield sse(
            "error",
            {"code": "PLAN_GENERATION_FAILED", "message": "生成失败，请稍后再试", "retryable": True},
        )
    finally:
        if db is not None:
            await db.close()
