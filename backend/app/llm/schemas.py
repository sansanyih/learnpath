"""Structured output schemas for the generation pipeline."""

from typing import Literal

from pydantic import BaseModel, Field


class KnowledgePointIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    objective: str = Field(min_length=1, max_length=300)


class PhaseSkeletonIn(BaseModel):
    id: str = Field(pattern=r"^p\d{1,2}$")
    title: str = Field(min_length=1, max_length=80)
    days: int = Field(ge=1, le=60)
    focus: str = Field(min_length=1, max_length=200)
    prerequisites: list[str] = Field(default_factory=list)
    knowledge_points: list[KnowledgePointIn] = Field(min_length=3, max_length=5)
    deliverable: str = Field(default="", max_length=300)


class SkeletonOut(BaseModel):
    phases: list[PhaseSkeletonIn] = Field(min_length=4, max_length=8)
    assumptions: list[str] = Field(default_factory=list)


class TaskIn(BaseModel):
    day_offset: int = Field(ge=0, le=60)
    title: str = Field(min_length=1, max_length=160)
    type: Literal["reading", "coding", "quiz", "review", "writing"] = "reading"
    duration_min: int = Field(ge=5, le=180)
    resource: str = Field(default="", max_length=300)
    acceptance: str = Field(default="", max_length=300)


class PhaseDetailOut(BaseModel):
    tasks: list[TaskIn] = Field(min_length=1, max_length=60)
