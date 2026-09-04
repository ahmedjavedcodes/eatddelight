from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db, require_role
from app.models import AdminRole
from app.schemas.contact import ContactMessageRead, ContactMessageReadUpdate
from app.services.contact import list_contact_messages, mark_read

router = APIRouter(
    prefix="/admin/contact-messages",
    tags=["admin:contact"],
    dependencies=[Depends(require_role(AdminRole.owner, AdminRole.staff))],
)


@router.get("", response_model=list[ContactMessageRead])
async def list_contact_messages_endpoint(
    db: Annotated[AsyncSession, Depends(get_db)],
    is_read: bool | None = Query(default=None),
) -> list[ContactMessageRead]:
    messages = await list_contact_messages(db, is_read=is_read)
    return [ContactMessageRead.model_validate(m) for m in messages]


@router.patch("/{message_id}", response_model=ContactMessageRead)
async def update_contact_message_endpoint(
    message_id: int,
    payload: ContactMessageReadUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContactMessageRead:
    message = await mark_read(db, message_id, payload.is_read)
    return ContactMessageRead.model_validate(message)
