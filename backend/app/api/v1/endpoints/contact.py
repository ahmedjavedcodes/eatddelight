from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db
from app.schemas.contact import ContactMessageCreate, ContactMessageRead
from app.services.contact import create_contact_message

router = APIRouter(prefix="/contact", tags=["contact"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ContactMessageRead)
async def submit_contact_message(
    payload: ContactMessageCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContactMessageRead:
    message = await create_contact_message(db, payload)
    return ContactMessageRead.model_validate(message)
