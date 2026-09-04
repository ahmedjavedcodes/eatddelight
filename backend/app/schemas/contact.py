from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class ContactMessageCreate(BaseModel):
    name: Annotated[str, Field(max_length=120)]
    phone_or_email: Annotated[str, Field(max_length=255)]
    message: Annotated[str, Field(min_length=1, max_length=4000)]


class ContactMessageReadUpdate(BaseModel):
    is_read: bool


class ContactMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone_or_email: str
    message: str
    is_read: bool
    created_at: datetime
