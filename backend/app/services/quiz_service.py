"""Phase quiz generation, grading, mastery updates and plan adjustments."""

import json
from datetime import timedelta
from string import Template

from sqlalchemy import select

from app.core.sse import sse  # noqa: F401  (kept for potential streaming)
from app.db.database import SessionLocal
from app.db.models import (
    Attempt,
    Goal,
    KnowledgePoint,
    Mastery,
    Phase,
    Plan,
    PlanAdjustment,
    Quiz,
    ReviewItem,
    Task,
    utcnow,
)
from app.llm.client import LlmError, get_llm
from app.llm.json_call import call_json
from app.llm.prompts import load_prompt
from app.llm.quiz_schemas import DimsOut, GradeOut, QuizGenOut
from app.llm.usage import record_usage


class QuizError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _normalize_choice(value: str, options: list[str]) -> str:
    text = (value or "").strip()
    upper = text.upper()
    if upper and upper[0] in "ABCD" and len(upper) <= 2:
        return upper[0]
    for index, option in enumerate(options or []):
        if text == str(option).strip():
            return "ABCD"[index]
        if upper == f"{'ABCD'[index]}".upper():
            return "ABCD"[index]
    return upper[:1]


def _fallback_grade(answer: str, reference: str) -> GradeOut:
    answer_text = (answer or "").strip()
    reference_text = (reference or "").strip()
    if not answer_text:
        return GradeOut(
            score=0,
            dims=DimsOut(technical=0, principle=0, coverage=0, structure=0),
            feedback="没有作答，先用自己的话写三条要点。",
        )
    tokens = [token for token in reference_text.replace("。", " ").split() if len(token) >= 2]
    hit = sum(1 for token in tokens if token in answer_text)
    ratio = hit / len(tokens) if tokens else min(1.0, len(answer_text) / 80)
    score = max(20, min(85, int(20 + ratio * 65)))
    return GradeOut(
        score=score,
        dims=DimsOut(
            technical=score,
            principle=max(15, score - 10),
            coverage=max(15, score - 5),
            structure=max(20, score - 5),
        ),
        feedback="评分服务暂时不可用，这里按关键点覆盖做了粗略估计。",
    )


async def _grade_open(question: Quiz, answer: str) -> tuple[GradeOut, list]:
    system, template = load_prompt("grade_answer_v1.txt")
    user = Template(template).substitute(
        question=question.question,
        reference=question.answer,
        answer=answer or "（未作答）",
    )
    try:
        result, usages = await call_json(
            purpose="quiz_grade",
            system=system,
            user=user,
            schema_cls=GradeOut,
            llm=get_llm(),
            temperature=0.1,
            max_tokens=800,
        )
        return result, usages
    except LlmError:
        return _fallback_grade(answer, question.answer), []


def _decide(score: int, phase_title: str, kp_names: list[str]) -> tuple[str, str, list[dict]]:
    kp_text = "、".join(kp_names[:3]) or phase_title
    short = kp_names[0] if kp_names else phase_title
    if score >= 90:
        return "skip", "掌握得很扎实，可以跳过本阶段剩余任务，直接进入下一阶段。", []
    if score >= 85:
        return "mastered", "已经掌握，安排 7 天后再复习一次即可。", []
    if score >= 70:
        return "continue", "继续下一阶段，3 天后安排一次复习。", []
    if score >= 60:
        return (
            "review",
            f"有缺口，3 天内复习「{kp_text}」，并补 1 道变式题。",
            [{"title": f"复习：{phase_title} 的错题", "type": "review", "duration_min": 20}],
        )
    if score >= 40:
        return (
            "remediate",
            f"基础不牢，先补「{kp_text}」：插入 2 条加练任务，再继续后续阶段。",
            [
                {"title": f"重读：{short} 的关键概念", "type": "reading", "duration_min": 25},
                {"title": f"加练：{short} 基础题", "type": "quiz", "duration_min": 20},
            ],
        )
    return (
        "remediate_plus",
        f"得分偏低，回到学习状态：先补「{kp_text}」，再重做一次本阶段测验。",
        [
            {"title": f"重读：{short} 的关键概念", "type": "reading", "duration_min": 30},
            {"title": f"加练：{short} 基础题", "type": "quiz", "duration_min": 20},
            {"title": f"重做：{phase_title} 阶段测验", "type": "quiz", "duration_min": 20},
        ],
    )


async def _apply_mastery(db, user_id: str, kp_id: str | None, score: int) -> None:
    if not kp_id:
        return
    now = utcnow()
    mastery = await db.scalar(
        select(Mastery).where(Mastery.user_id == user_id, Mastery.kp_id == kp_id)
    )
    if mastery is None:
        mastery = Mastery(user_id=user_id, kp_id=kp_id, score=0.0, attempts=0, ease=2.5)
        db.add(mastery)
        await db.flush()

    norm = score / 100
    mastery.score = max(0.0, min(1.0, 0.5 * norm + 0.5 * (mastery.score or norm)))
    mastery.attempts += 1
    mastery.last_score = score
    if mastery.score >= 0.85:
        mastery.status = "mastered"
    elif mastery.score >= 0.6:
        mastery.status = "learning"
    else:
        mastery.status = "review"

    interval = 1 if score < 60 else 3 if score < 70 else 7 if score < 85 else 15
    mastery.interval_days = interval
    mastery.due_at = now + timedelta(days=interval)
    mastery.updated_at = now

    item = await db.scalar(
        select(ReviewItem).where(ReviewItem.user_id == user_id, ReviewItem.kp_id == kp_id)
    )
    if item is None:
        item = ReviewItem(user_id=user_id, kp_id=kp_id)
        db.add(item)
    item.due_at = mastery.due_at
    item.interval_days = interval
    item.ease = mastery.ease
    item.last_result = "good" if score >= 70 else "hard"


async def get_or_create_phase_quiz(plan_id: str, phase_id: str, user_id: str) -> dict:
    async with SessionLocal() as db:
        phase = await db.get(Phase, phase_id)
        plan = await db.get(Plan, plan_id)
        if phase is None or plan is None or plan.id != phase.plan_id:
            raise QuizError("PHASE_NOT_FOUND", "阶段不存在", 404)
        goal = await db.get(Goal, plan.goal_id)
        if goal is None or goal.user_id != user_id:
            raise QuizError("PHASE_NOT_FOUND", "阶段不存在", 404)

        existing = (
            await db.scalars(
                select(Quiz).where(Quiz.phase_id == phase_id).order_by(Quiz.seq)
            )
        ).all()
        if existing:
            return {
                "phase_id": phase.id,
                "phase_title": phase.title,
                "questions": [
                    {
                        "id": quiz.id,
                        "type": quiz.type,
                        "question": quiz.question,
                        "options": quiz.options or [],
                        "difficulty": quiz.difficulty,
                    }
                    for quiz in existing
                ],
            }

        kps = (
            await db.scalars(
                select(KnowledgePoint)
                .where(KnowledgePoint.phase_id == phase_id)
                .order_by(KnowledgePoint.seq)
            )
        ).all()
        names = [kp.name for kp in kps]
        phase_json = json.dumps(
            {
                "title": phase.title,
                "days": phase.days,
                "focus": phase.focus,
                "knowledge_points": [{"name": kp.name, "objective": kp.objective} for kp in kps],
            },
            ensure_ascii=False,
        )

        def validate(out: QuizGenOut) -> None:
            choices = [item for item in out.questions if item.type == "choice"]
            opens = [item for item in out.questions if item.type == "open"]
            if len(choices) != 3 or len(opens) != 2:
                raise ValueError("必须是 3 道选择题 + 2 道简答题")
            for item in choices:
                if len(item.options) != 4 or item.answer.strip().upper()[:1] not in "ABCD":
                    raise ValueError(f"选择题「{item.question}」的选项或答案不合法")
            for item in out.questions:
                if names and not any(
                    item.kp == name or item.kp in name or name in item.kp for name in names
                ):
                    raise ValueError(f"知识点「{item.kp}」不在本阶段知识点里")

        system, template = load_prompt("phase_quiz_v1.txt")
        user = Template(template).substitute(phase_json=phase_json)
        out, usages = await call_json(
            purpose="phase_quiz",
            system=system,
            user=user,
            schema_cls=QuizGenOut,
            llm=get_llm(),
            extra_validate=validate,
            temperature=0.5,
            max_tokens=2200,
        )
        for usage in usages:
            record_usage(db, user_id, "phase_quiz", usage)

        name_to_id = {kp.name: kp.id for kp in kps}
        for seq, item in enumerate(out.questions, start=1):
            kp_id = None
            for name, kid in name_to_id.items():
                if item.kp == name or item.kp in name or name in item.kp:
                    kp_id = kid
                    break
            db.add(
                Quiz(
                    plan_id=plan_id,
                    phase_id=phase_id,
                    kp_id=kp_id,
                    type=item.type,
                    question=item.question,
                    options=item.options,
                    answer=item.answer,
                    explanation=item.explanation,
                    seq=seq,
                    difficulty=2,
                )
            )
        await db.commit()

        quizzes = (
            await db.scalars(
                select(Quiz).where(Quiz.phase_id == phase_id).order_by(Quiz.seq)
            )
        ).all()
        return {
            "phase_id": phase.id,
            "phase_title": phase.title,
            "questions": [
                {
                    "id": quiz.id,
                    "type": quiz.type,
                    "question": quiz.question,
                    "options": quiz.options or [],
                    "difficulty": quiz.difficulty,
                }
                for quiz in quizzes
            ],
        }


async def submit_phase_quiz(phase_id: str, user_id: str, answers: list[dict]) -> dict:
    async with SessionLocal() as db:
        phase = await db.get(Phase, phase_id)
        plan = await db.get(Plan, phase.plan_id) if phase else None
        if phase is None or plan is None:
            raise QuizError("PHASE_NOT_FOUND", "阶段不存在", 404)
        goal = await db.get(Goal, plan.goal_id)
        if goal is None or goal.user_id != user_id:
            raise QuizError("PHASE_NOT_FOUND", "阶段不存在", 404)
        plan_id = plan.id

        quizzes = (
            await db.scalars(
                select(Quiz).where(Quiz.phase_id == phase_id).order_by(Quiz.seq)
            )
        ).all()
        if not quizzes:
            raise QuizError("QUIZ_NOT_FOUND", "还没有生成测验", 404)

        answer_map = {item["quiz_id"]: item.get("answer", "") for item in answers}
        results = []
        total = 0
        dims_sum = {"technical": 0, "principle": 0, "coverage": 0, "structure": 0}
        dims_count = 0
        usage_cost = 0.0

        for quiz in quizzes:
            raw_answer = answer_map.get(quiz.id, "")
            if quiz.type == "choice":
                expected = _normalize_choice(quiz.answer, quiz.options or [])
                actual = _normalize_choice(raw_answer, quiz.options or [])
                score = 100 if expected and actual and expected == actual else 0
                dims = {
                    "technical": score,
                    "principle": score,
                    "coverage": score,
                    "structure": score,
                }
                feedback = (
                    "选择题判断正确。"
                    if score == 100
                    else f"选择题判断错误，正确答案是 {expected}。"
                )
                reference = quiz.answer
            else:
                graded, usages = await _grade_open(quiz, raw_answer)
                score = graded.score
                dims = graded.dims.model_dump()
                feedback = graded.feedback
                reference = quiz.answer
                for usage in usages:
                    usage_cost += record_usage(db, user_id, "quiz_grade", usage)

            db.add(
                Attempt(
                    user_id=user_id,
                    quiz_id=quiz.id,
                    phase_id=phase_id,
                    answer=raw_answer,
                    score=score,
                    dims=dims,
                    feedback=feedback,
                )
            )
            total += score
            for key in dims_sum:
                dims_sum[key] += dims[key]
            dims_count += 1
            await _apply_mastery(db, user_id, quiz.kp_id, score)

            results.append(
                {
                    "quiz_id": quiz.id,
                    "question": quiz.question,
                    "type": quiz.type,
                    "answer": raw_answer,
                    "score": score,
                    "dims": dims,
                    "feedback": feedback,
                    "reference": reference,
                    "explanation": quiz.explanation,
                }
            )

        phase_score = round(total / len(quizzes))
        dims = {key: round(value / dims_count) for key, value in dims_sum.items()}
        kp_names = [
            kp.name
            for kp in (
                await db.scalars(
                    select(KnowledgePoint).where(KnowledgePoint.phase_id == phase_id)
                )
            ).all()
        ]
        action, message, tasks = _decide(phase_score, phase.title, kp_names)

        adjustment = None
        if action in {"skip", "review", "remediate", "remediate_plus"}:
            row = PlanAdjustment(
                user_id=user_id,
                plan_id=plan_id,
                phase_id=phase_id,
                action=action,
                payload={"message": message, "tasks": tasks},
                status="pending",
            )
            db.add(row)
            await db.flush()
            adjustment = {
                "id": row.id,
                "action": action,
                "message": message,
                "tasks": [task["title"] for task in tasks],
            }

        await db.commit()
        return {
            "phase_id": phase_id,
            "score": phase_score,
            "dims": dims,
            "results": results,
            "adjustment": adjustment,
            "cost_est": round(usage_cost, 4),
        }


async def adopt_adjustment(adjustment_id: str, user_id: str) -> dict:
    async with SessionLocal() as db:
        row = await db.get(PlanAdjustment, adjustment_id)
        if row is None or row.user_id != user_id:
            raise QuizError("ADJUSTMENT_NOT_FOUND", "调整不存在", 404)
        if row.status != "pending":
            return {"ok": True, "status": row.status, "inserted": 0}

        phase = await db.get(Phase, row.phase_id)
        if phase is None:
            raise QuizError("ADJUSTMENT_NOT_FOUND", "调整不存在", 404)

        inserted = 0
        deleted = 0
        if row.action == "skip":
            phase.status = "done"
            for task in (
                await db.scalars(select(Task).where(Task.phase_id == phase.id))
            ).all():
                if task.status != "done":
                    task.status = "done"
                    task.completed_at = utcnow()
                    inserted += 0
                    deleted += 1
        else:
            tasks = (row.payload or {}).get("tasks", [])
            existing = (
                await db.scalars(select(Task).where(Task.phase_id == phase.id))
            ).all()
            next_offset = max((task.day_offset for task in existing), default=0) + 1
            for item in tasks:
                db.add(
                    Task(
                        phase_id=phase.id,
                        day_offset=next_offset,
                        title=item.get("title", "加练"),
                        type=item.get("type", "review"),
                        duration_min=int(item.get("duration_min", 20)),
                        resource="",
                        acceptance="完成并复盘",
                        repo_paths=[],
                    )
                )
                inserted += 1
            if row.action.startswith("remediate"):
                phase.status = "doing"

        row.status = "applied"
        await db.commit()
        return {"ok": True, "status": "applied", "inserted": inserted, "completed_tasks": deleted}


async def ignore_adjustment(adjustment_id: str, user_id: str) -> dict:
    async with SessionLocal() as db:
        row = await db.get(PlanAdjustment, adjustment_id)
        if row is None or row.user_id != user_id:
            raise QuizError("ADJUSTMENT_NOT_FOUND", "调整不存在", 404)
        row.status = "ignored"
        await db.commit()
        return {"ok": True, "status": "ignored"}
