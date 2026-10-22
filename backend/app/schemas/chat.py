"""Chat request schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatIn(BaseModel):
    scope: Literal["chapter", "task"]
    context_id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=2, max_length=800)
    history: list[ChatMessage] = Field(default_factory=list)
