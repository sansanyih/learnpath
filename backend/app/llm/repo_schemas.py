"""Structured output schemas for repo ingestion."""

from pydantic import BaseModel, Field


class RepoProfileOut(BaseModel):
    language: str = ""
    framework: str = ""
    summary: str = ""
    entrypoints: list[str] = Field(default_factory=list)
    module_map: list[str] = Field(default_factory=list)
    reading_order: list[str] = Field(default_factory=list)


class ChapterPlanItem(BaseModel):
    title: str = Field(min_length=2, max_length=80)
    purpose: str = Field(min_length=4, max_length=300)
    files: list[str] = Field(min_length=1, max_length=6)
    concepts: list[str] = Field(min_length=2, max_length=5)


class ChapterPlanOut(BaseModel):
    chapters: list[ChapterPlanItem] = Field(min_length=3, max_length=9)


class ChapterContentOut(BaseModel):
    markdown: str = Field(min_length=100)
