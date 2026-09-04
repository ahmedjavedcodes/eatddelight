from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidStatusTransitionError, NotACustomOrderError, NotFoundError
from app.models import Order, OrderSource, OrderStatus
from app.schemas.admin import OrderQuoteUpdate, OrderStatusUpdate

ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.pending: {OrderStatus.confirmed, OrderStatus.cancelled},
    OrderStatus.confirmed: {OrderStatus.completed, OrderStatus.cancelled},
    OrderStatus.completed: set(),
    OrderStatus.cancelled: set(),
}


async def get_order_or_404(session: AsyncSession, order_id: int) -> Order:
    order = await session.get(Order, order_id)
    if order is None:
        raise NotFoundError("order not found")
    return order


async def set_order_status(
    session: AsyncSession, order_id: int, payload: OrderStatusUpdate
) -> Order:
    order = await get_order_or_404(session, order_id)
    if payload.status != order.status and payload.status not in ALLOWED_TRANSITIONS[order.status]:
        raise InvalidStatusTransitionError(
            f"cannot transition order from '{order.status}' to '{payload.status}'"
        )
    order.status = payload.status
    if payload.admin_notes is not None:
        order.admin_notes = payload.admin_notes
    await session.flush()
    await session.refresh(order)
    return order


async def quote_custom_order(
    session: AsyncSession, order_id: int, payload: OrderQuoteUpdate
) -> Order:
    order = await get_order_or_404(session, order_id)
    if order.order_source != OrderSource.custom_request:
        raise NotACustomOrderError("order is not a custom request")
    order.total = payload.total
    order.subtotal = payload.subtotal if payload.subtotal is not None else payload.total
    if order.status == OrderStatus.pending:
        order.status = OrderStatus.confirmed
    await session.flush()
    await session.refresh(order)
    return order
