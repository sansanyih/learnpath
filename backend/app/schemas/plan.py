"""Plan list / detail schemas."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class TaskOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    day_offset: int
    title: str
    type: str
    duration_min: int
    resource: str
    acceptance: str
    status: str


class KnowledgePointOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    name: str
    objective: str
    seq: int


class PhaseOut(BaseModel):
    id: str
    seq: int
    title: str
    days: int
    focus: str
    deliverable: str
    status: str
    knowledge_points: list[KnowledgePointOut]
    tasks: list[TaskOut]


class PlanDetailOut(BaseModel):
    id: str
    goal_title: str
    goal_raw: str
    daily_minutes: int
    level: str
    deadline: date | None
    status: str
    created_at: datetime
    phases: list[PhaseOut]


class PlanSummary(BaseModel):
    id: str
    goal_title: str
    status: str
    created_at: datetime
    phase_count: int
    task_count: int


class TaskStatusIn(BaseModel):
    status: Literal["todo", "done"]
