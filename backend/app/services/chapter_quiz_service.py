"""Chapter quiz: generation, grading, latest attempt."""

import json
from string import Template

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import (
    Chapter,
    ChapterProgress,
    ChapterQuiz,
    ChapterQuizAttempt,
    Goal,
    Plan,
)
from app.llm.client import get_llm
from app.llm.json_call import call_json
from app.llm.prompts import load_prompt
from app.llm.quiz_schemas import QuizGenOut
from app.llm.usage import record_usage
from app.services.quiz_service import _grade_open, _normalize_choice


class ChapterQuizError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


async def _owned_chapter(db, chapter_id: str, user_id: str) -> Chapter:
    chapter = await db.get(Chapter, chapter_id)
    if chapter is None:
        raise ChapterQuizError("CHAPTER_NOT_FOUND", "章节不存在", 404)
    plan = await db.get(Plan, chapter.plan_id)
    goal = await db.get(Goal, plan.goal_id) if plan else None
    if plan is None or goal is None or goal.user_id != user_id:
        raise ChapterQuizError("CHAPTER_NOT_FOUND", "章节不存在", 404)
    return chapter


async def get_or_create_chapter_quiz(chapter_id: str, user_id: str) -> dict:
    async with SessionLocal() as db:
        chapter = await _owned_chapter(db, chapter_id, user_id)
        existing = (
            await db.scalars(
                select(ChapterQuiz).where(ChapterQuiz.chapter_id == chapter_id).order_by(ChapterQuiz.seq)
            )
        ).all()
        if existing:
            return {
                "chapter_id": chapter.id,
                "chapter_title": chapter.title,
                "questions": [
                    {
                        "id": quiz.id,
                        "type": quiz.type,
                        "question": quiz.question,
                        "options": quiz.options or [],
                        "difficulty": 2,
                    }
                    for quiz in existing
                ],
            }

        system, template = load_prompt("chapter_quiz_v1.txt")
        user = Template(template).substitute(
            chapter_json=json.dumps(
                {
                    "title": chapter.title,
                    "purpose": chapter.purpose,
                    "concepts": chapter.concepts or [],
                    "files": chapter.files or [],
                    "content": (chapter.content_md or "")[:5000],
                },
                ensure_ascii=False,
            )
        )

        def validate(out: QuizGenOut) -> None:
            choices = [item for item in out.questions if item.type == "choice"]
            opens = [item for item in out.questions if item.type == "open"]
            if len(choices) != 3 or len(opens) != 2:
                raise ValueError("必须是 3 道选择题 + 2 道简答题")
            for item in choices:
                if len(item.options) != 4 or item.answer.strip().upper()[:1] not in "ABCD":
                    raise ValueError(f"选择题「{item.question}」的选项或答案不合法")

        out, usages = await call_json(
            purpose="chapter_quiz",
            system=system,
            user=user,
            schema_cls=QuizGenOut,
            llm=get_llm(),
            extra_validate=validate,
            temperature=0.5,
            max_tokens=2200,
        )
        for usage in usages:
            record_usage(db, user_id, "chapter_quiz", usage)

        for seq, item in enumerate(out.questions, start=1):
            db.add(
                ChapterQuiz(
                    chapter_id=chapter_id,
                    type=item.type,
                    question=item.question,
                    options=item.options,
                    answer=item.answer,
                    explanation=item.explanation,
                    seq=seq,
                )
            )
        await db.commit()

        quizzes = (
            await db.scalars(
                select(ChapterQuiz).where(ChapterQuiz.chapter_id == chapter_id).order_by(ChapterQuiz.seq)
            )
        ).all()
        return {
            "chapter_id": chapter.id,
            "chapter_title": chapter.title,
            "questions": [
                {
                    "id": quiz.id,
                    "type": quiz.type,
                    "question": quiz.question,
                    "options": quiz.options or [],
                    "difficulty": 2,
                }
                for quiz in quizzes
            ],
        }


async def submit_chapter_quiz(chapter_id: str, user_id: str, answers: list[dict]) -> dict:
    async with SessionLocal() as db:
        chapter = await _owned_chapter(db, chapter_id, user_id)
        quizzes = (
            await db.scalars(
                select(ChapterQuiz).where(ChapterQuiz.chapter_id == chapter_id).order_by(ChapterQuiz.seq)
            )
        ).all()
        if not quizzes:
            raise ChapterQuizError("QUIZ_NOT_FOUND", "还没有生成测验", 404)

        answer_map = {item["quiz_id"]: item.get("answer", "") for item in answers}
        results = []
        total = 0
        dims_sum = {"technical": 0, "principle": 0, "coverage": 0, "structure": 0}

        for quiz in quizzes:
            raw = answer_map.get(quiz.id, "")
            if quiz.type == "choice":
                expected = _normalize_choice(quiz.answer, quiz.options or [])
                actual = _normalize_choice(raw, quiz.options or [])
                score = 100 if expected and actual and expected == actual else 0
                dims = {"technical": score, "principle": score, "coverage": score, "structure": score}
                feedback = "选择题判断正确。" if score == 100 else f"选择题判断错误，正确答案是 {expected}。"
                reference = quiz.answer
            else:
                graded, usages = await _grade_open(quiz, raw)
                score = graded.score
                dims = graded.dims.model_dump()
                feedback = graded.feedback
                reference = quiz.answer
                for usage in usages:
                    record_usage(db, user_id, "chapter_quiz_grade", usage)

            db.add(
                ChapterQuizAttempt(
                    user_id=user_id,
                    chapter_id=chapter_id,
                    quiz_id=quiz.id,
                    answer=raw,
                    score=score,
                    dims=dims,
                    feedback=feedback,
                )
            )
            total += score
            for key in dims_sum:
                dims_sum[key] += dims[key]
            results.append(
                {
                    "quiz_id": quiz.id,
                    "question": quiz.question,
                    "type": quiz.type,
                    "answer": raw,
                    "score": score,
                    "dims": dims,
                    "feedback": feedback,
                    "reference": reference,
                    "explanation": quiz.explanation,
                }
            )

        overall = round(total / len(quizzes))
        dims = {key: round(value / len(quizzes)) for key, value in dims_sum.items()}

        progress = await db.scalar(
            select(ChapterProgress).where(
                ChapterProgress.user_id == user_id, ChapterProgress.chapter_id == chapter_id
            )
        )
        status = "mastered" if overall >= 85 else "learning" if overall >= 60 else "review"
        if progress is None:
            db.add(ChapterProgress(user_id=user_id, chapter_id=chapter_id, status=status))
        else:
            progress.status = status

        await db.commit()
        return {
            "chapter_id": chapter_id,
            "score": overall,
            "dims": dims,
            "results": results,
            "status": status,
        }


async def latest_chapter_attempt(chapter_id: str, user_id: str) -> dict:
    async with SessionLocal() as db:
        chapter = await _owned_chapter(db, chapter_id, user_id)
        attempts = (
            await db.scalars(
                select(ChapterQuizAttempt)
                .where(
                    ChapterQuizAttempt.chapter_id == chapter_id,
                    ChapterQuizAttempt.user_id == user_id,
                )
                .order_by(ChapterQuizAttempt.created_at.desc())
                .limit(10)
            )
        ).all()
        if not attempts:
            return {"chapter_id": chapter.id, "score": None, "results": []}

        quizzes = {
            quiz.id: quiz
            for quiz in (
                await db.scalars(select(ChapterQuiz).where(ChapterQuiz.chapter_id == chapter_id))
            ).all()
        }
        latest: list[dict] = []
        seen: set[str] = set()
        for attempt in attempts:
            if attempt.quiz_id in seen:
                continue
            seen.add(attempt.quiz_id)
            quiz = quizzes.get(attempt.quiz_id)
            latest.append(
                {
                    "quiz_id": attempt.quiz_id,
                    "question": quiz.question if quiz else "",
                    "type": quiz.type if quiz else "open",
                    "score": attempt.score,
                    "feedback": attempt.feedback,
                    "reference": quiz.answer if quiz else "",
                }
            )
        scores = [item["score"] for item in latest]
        return {
            "chapter_id": chapter.id,
            "score": round(sum(scores) / len(scores)) if scores else None,
            "results": latest,
        }
