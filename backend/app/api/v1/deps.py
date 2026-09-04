from typing import Annotated

from fastapi import Header

from app.db.session import get_db

__all__ = ["get_db", "get_session_token"]


async def get_session_token(
    x_session_token: Annotated[str, Header(min_length=1)],
) -> str:
    """The anonymous customer's opaque bucket key. Presence-checked only."""
    return x_session_token
