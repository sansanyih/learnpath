"""Structured task guide output."""

from pydantic import BaseModel, Field


class MaterialOut(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    url: str = Field(default="", max_length=300)
    kind: str = Field(default="doc", max_length=16)


class ConceptOut(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    explanation: str = Field(min_length=10, max_length=600)


class CodeExampleOut(BaseModel):
    title: str = Field(min_length=2, max_length=80)
    language: str = Field(default="python", max_length=20)
    code: str = Field(min_length=10, max_length=4000)
    note: str = Field(default="", max_length=300)


class TaskGuideOut(BaseModel):
    steps: list[str] = Field(min_length=3, max_length=5)
    concepts: list[ConceptOut] = Field(min_length=2, max_length=5)
    code_examples: list[CodeExampleOut] = Field(default_factory=list, max_length=3)
    materials: list[MaterialOut] = Field(min_length=1, max_length=5)
    search_queries: list[str] = Field(min_length=1, max_length=4)
    self_check: list[str] = Field(min_length=2, max_length=4)
    pitfalls: list[str] = Field(default_factory=list, max_length=4)
