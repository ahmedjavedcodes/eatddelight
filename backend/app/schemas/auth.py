from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AdminRole


class LoginRequest(BaseModel):
    email: Annotated[str, Field(max_length=255)]
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: AdminRole
    is_active: bool
    created_at: datetime


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: AdminUserRead
