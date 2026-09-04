from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db, require_role
from app.models import AdminRole, AdminUser, Order, OrderSource, OrderStatus
from app.schemas.admin import OrderQuoteUpdate, OrderRead, OrderStatusUpdate
from app.services.admin_orders import get_order_or_404, quote_custom_order, set_order_status

router = APIRouter(prefix="/admin/orders", tags=["admin:orders"])


@router.get("", response_model=list[OrderRead])
async def list_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner, AdminRole.staff))],
    status: Annotated[OrderStatus | None, Query()] = None,
    order_source: Annotated[OrderSource | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(le=200, ge=1)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[OrderRead]:
    stmt = select(Order).order_by(Order.created_at.desc()).limit(limit).offset(offset)
    if status is not None:
        stmt = stmt.where(Order.status == status)
    if order_source is not None:
        stmt = stmt.where(Order.order_source == order_source)
    if date_from is not None:
        stmt = stmt.where(Order.requested_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Order.requested_date <= date_to)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                Order.customer_name.ilike(pattern),
                Order.customer_phone.ilike(pattern),
                Order.invoice_number.ilike(pattern),
            )
        )
    result = await db.execute(stmt)
    return [OrderRead.model_validate(o) for o in result.scalars().all()]


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner, AdminRole.staff))],
) -> OrderRead:
    order = await get_order_or_404(db, order_id)
    return OrderRead.model_validate(order)


@router.patch("/{order_id}/status", response_model=OrderRead)
async def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner, AdminRole.staff))],
) -> OrderRead:
    order = await set_order_status(db, order_id, payload)
    return OrderRead.model_validate(order)


@router.patch("/{order_id}/quote", response_model=OrderRead)
async def quote_order(
    order_id: int,
    payload: OrderQuoteUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[AdminUser, Depends(require_role(AdminRole.owner))],
) -> OrderRead:
    order = await quote_custom_order(db, order_id, payload)
    return OrderRead.model_validate(order)
