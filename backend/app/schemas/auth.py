"""Request / response schemas."""

from datetime import date

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    display_name: str | None = Field(default=None, max_length=64)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    email: str
    display_name: str | None = None
    role: str = "user"


class TokenOut(BaseModel):
    token: str
    user: UserOut


class PlanIn(BaseModel):
    goal: str = Field(min_length=4, max_length=500)
    deadline: date | None = None
    daily_minutes: int = Field(default=45, ge=15, le=120)
    level: str = Field(default="beginner", pattern="^(beginner|intermediate|advanced)$")


class ChangePasswordIn(BaseModel):
    old_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)
