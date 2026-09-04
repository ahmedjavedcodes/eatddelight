from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models import ContactMessage
from app.schemas.contact import ContactMessageCreate


async def create_contact_message(
    session: AsyncSession, payload: ContactMessageCreate
) -> ContactMessage:
    message = ContactMessage(
        name=payload.name,
        phone_or_email=payload.phone_or_email,
        message=payload.message,
        is_read=False,
    )
    session.add(message)
    await session.flush()
    return message


async def list_contact_messages(
    session: AsyncSession, *, is_read: bool | None = None
) -> list[ContactMessage]:
    stmt = select(ContactMessage).order_by(ContactMessage.created_at.desc())
    if is_read is not None:
        stmt = stmt.where(ContactMessage.is_read == is_read)
    return list((await session.execute(stmt)).scalars().all())


async def mark_read(session: AsyncSession, message_id: int, is_read: bool) -> ContactMessage:
    message = await session.get(ContactMessage, message_id)
    if message is None:
        raise NotFoundError("contact message not found")
    message.is_read = is_read
    await session.flush()
    return message
