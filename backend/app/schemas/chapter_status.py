"""Chapter reading status."""

from typing import Literal

from pydantic import BaseModel


class ChapterStatusIn(BaseModel):
    status: Literal["todo", "learning", "review", "mastered"]
