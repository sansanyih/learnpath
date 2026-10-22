"""Chat history and annotation schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class AnnotationIn(BaseModel):
    scope: Literal["chapter", "task"]
    context_id: str = Field(min_length=1, max_length=64)
    content: str = Field(min_length=2, max_length=4000)
