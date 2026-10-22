"""Quiz / grading / adjustment API schemas."""

from pydantic import BaseModel, Field


class QuizPublic(BaseModel):
    id: str
    type: str
    question: str
    options: list[str]
    difficulty: int


class PhaseQuizOut(BaseModel):
    phase_id: str
    phase_title: str
    questions: list[QuizPublic]


class AnswerIn(BaseModel):
    quiz_id: str
    answer: str = ""


class SubmitIn(BaseModel):
    phase_id: str
    answers: list[AnswerIn] = Field(default_factory=list)


class QuestionResult(BaseModel):
    quiz_id: str
    question: str
    type: str
    answer: str
    score: int
    dims: dict
    feedback: str
    reference: str
    explanation: str


class AdjustmentOut(BaseModel):
    id: str
    action: str
    message: str
    tasks: list[str]


class SubmitOut(BaseModel):
    phase_id: str
    score: int
    dims: dict
    results: list[QuestionResult]
    adjustment: AdjustmentOut | None = None
    cost_est: float = 0.0
