"""Structured schemas for quiz generation and grading."""

from typing import Literal

from pydantic import BaseModel, Field


class QuizItemIn(BaseModel):
    type: Literal["choice", "open"]
    question: str = Field(min_length=5, max_length=400)
    options: list[str] = Field(default_factory=list)
    answer: str = Field(min_length=1, max_length=400)
    explanation: str = Field(default="", max_length=600)
    kp: str = Field(default="", max_length=80)


class QuizGenOut(BaseModel):
    questions: list[QuizItemIn] = Field(min_length=5, max_length=5)


class DimsOut(BaseModel):
    technical: int = Field(ge=0, le=100)
    principle: int = Field(ge=0, le=100)
    coverage: int = Field(ge=0, le=100)
    structure: int = Field(ge=0, le=100)


class GradeOut(BaseModel):
    score: int = Field(ge=0, le=100)
    dims: DimsOut
    feedback: str = Field(min_length=2, max_length=600)
