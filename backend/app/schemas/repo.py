"""Repo import request/response schemas."""

from pydantic import BaseModel, Field


class RepoIn(BaseModel):
    url: str = Field(min_length=10, max_length=300)


class ChapterSummary(BaseModel):
    id: str
    seq: int
    title: str
    purpose: str
    files: list[str]
    concepts: list[str]
    status: str
    has_content: bool


class RepoSourceOut(BaseModel):
    id: str
    repo_full_name: str
    ref: str
    status: str
    file_count: int
    chapters: list[ChapterSummary]


class ChapterDetailOut(BaseModel):
    id: str
    plan_id: str
    repo_id: str
    seq: int
    title: str
    purpose: str
    files: list[str]
    concepts: list[str]
    status: str
    content_md: str | None
