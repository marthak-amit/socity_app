import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_session
from app.core.deps import SocietyContext, require_role
from app.core.errors import ApiError, not_found
from app.models import Membership, Order, OrderItem, User
from app.models.enums import OrderStatus, Role
from app.schemas.common import Page, PageParams
from app.schemas.orders import (
    BulkApproveIn,
    BulkApproveOut,
    OrderCreate,
    OrderOut,
    OrderSummary,
    PaymentSubmit,
    RejectIn,
)
from app.services import orders as svc
from app.services.audit import audit

router = APIRouter(prefix="/societies/{society_id}", tags=["orders"])

ORDER_LOAD = selectinload(Order.items).selectinload(OrderItem.tier)


async def _members_for(session: AsyncSession, society_id: uuid.UUID, orders: list[Order]):
    ids = {o.user_id for o in orders}
    if not ids:
        return {}
    rows = (await session.execute(
        select(User, Membership).outerjoin(
            Membership, (Membership.user_id == User.id) & (Membership.society_id == society_id)
        ).where(User.id.in_(ids))
    )).all()
    return {u.id: (u, m) for u, m in rows}


async def _serialise(session, ctx: SocietyContext, orders: list[Order], admin_view: bool) -> list[OrderOut]:
    members = await _members_for(session, ctx.sid, orders) if admin_view else None
    return await svc.orders_out(session, orders, ctx=ctx, admin_view=admin_view, members=members)


# ----------------------------------------------------------------------------------- member side
@router.post("/events/{event_id}/orders", response_model=OrderOut, status_code=201)
async def create_order(
    event_id: uuid.UUID, body: OrderCreate, ctx: SocietyContext = Depends(require_role(Role.MEMBER)),
    session: AsyncSession = Depends(get_session),
):
    order = await svc.create_order(session, ctx, event_id, body)
    await session.flush()
    loaded = await svc.lock_order(session, ctx.sid, order.id)
    return (await _serialise(session, ctx, [loaded], admin_view=False))[0]


@router.get("/orders/mine", response_model=Page[OrderOut])
async def my_orders(
    event_id: uuid.UUID | None = Query(None), page: PageParams = Depends(),
    ctx: SocietyContext = Depends(require_role(Role.MEMBER)), session: AsyncSession = Depends(get_session),
):
    conds = [Order.society_id == ctx.sid, Order.user_id == ctx.user.id]
    if event_id:
        conds.append(Order.event_id == event_id)
    total = await session.scalar(select(func.count()).select_from(Order).where(*conds))
    orders = (await session.scalars(
        select(Order).where(*conds).order_by(Order.created_at.desc()).limit(page.limit).offset(page.offset).options(ORDER_LOAD)
    )).all()
    return Page(items=await _serialise(session, ctx, list(orders), False), total=total, limit=page.limit, offset=page.offset)


@router.post("/orders/{order_id}/payment", response_model=OrderOut)
async def submit_payment(
    order_id: uuid.UUID, body: PaymentSubmit, ctx: SocietyContext = Depends(require_role(Role.MEMBER)),
    session: AsyncSession = Depends(get_session),
):
    order = await svc.lock_order(session, ctx.sid, order_id)
    if order.user_id != ctx.user.id:
        raise not_found("order_not_found", "Order not found")  # someone else's order: indistinguishable from missing
    await svc.submit_payment(session, ctx, order, body)
    await session.flush()
    return (await _serialise(session, ctx, [order], admin_view=False))[0]


@router.post("/orders/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(
    order_id: uuid.UUID, ctx: SocietyContext = Depends(require_role(Role.MEMBER)),
    session: AsyncSession = Depends(get_session),
):
    order = await svc.lock_order(session, ctx.sid, order_id)
    if order.user_id != ctx.user.id and not ctx.is_admin:
        raise not_found("order_not_found", "Order not found")
    await svc.cancel_order(session, ctx, order)
    return (await _serialise(session, ctx, [order], admin_view=ctx.is_admin and order.user_id != ctx.user.id))[0]


# ----------------------------------------------------------------------------------- admin queue
@router.get("/orders/summary", response_model=OrderSummary)
async def summary(
    event_id: uuid.UUID | None = Query(None), ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    conds = [Order.society_id == ctx.sid, Order.total_amount > 0]
    if event_id:
        conds.append(Order.event_id == event_id)
    rows = (await session.execute(
        select(Order.status, Order.payment_submitted_at.is_not(None), func.count(),
               func.count().filter(func.jsonb_array_length(Order.flags) > 0))
        .where(*conds).group_by(Order.status, Order.payment_submitted_at.is_not(None))
    )).all()
    s = dict(pending=0, pending_flagged=0, awaiting_payment=0, approved=0, rejected=0)
    for status, submitted, n, flagged in rows:
        if status == OrderStatus.PENDING:
            if submitted:
                s["pending"] += n
                s["pending_flagged"] += flagged
            else:
                s["awaiting_payment"] += n
        elif status in (OrderStatus.APPROVED, OrderStatus.REJECTED):
            s[status] += n
    return OrderSummary(**s)


@router.get("/orders", response_model=Page[OrderOut])
async def list_orders(
    status: OrderStatus | None = Query(OrderStatus.PENDING),
    event_id: uuid.UUID | None = Query(None),
    flagged: bool | None = Query(None),
    submitted: bool | None = Query(True, description="pending queue: only orders with payment proof"),
    q: str | None = Query(None, max_length=50),
    page: PageParams = Depends(),
    ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    conds = [Order.society_id == ctx.sid]
    if status:
        conds.append(Order.status == status.value)
    if event_id:
        conds.append(Order.event_id == event_id)
    if flagged is not None:
        cond = func.jsonb_array_length(Order.flags) > 0
        conds.append(cond if flagged else ~cond)
    if status == OrderStatus.PENDING and submitted is not None:
        conds.append(Order.payment_submitted_at.is_not(None) if submitted else Order.payment_submitted_at.is_(None))
    base = select(Order).where(*conds)
    count_q = select(func.count()).select_from(Order).where(*conds)
    if q:
        like = f"%{q.strip()}%"
        match = or_(Order.ref_code.ilike(like), Order.utr.ilike(like), User.name.ilike(like), User.phone.ilike(like))
        base = base.join(User, User.id == Order.user_id).where(match)
        count_q = count_q.join(User, User.id == Order.user_id).where(match)
    total = await session.scalar(count_q)
    order_by = Order.created_at.asc() if status == OrderStatus.PENDING else Order.created_at.desc()
    orders = (await session.scalars(base.order_by(order_by).limit(page.limit).offset(page.offset).options(ORDER_LOAD))).all()
    return Page(items=await _serialise(session, ctx, list(orders), True), total=total, limit=page.limit, offset=page.offset)


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: uuid.UUID, ctx: SocietyContext = Depends(require_role(Role.MEMBER)),
    session: AsyncSession = Depends(get_session),
):
    order = await session.scalar(select(Order).where(Order.id == order_id, Order.society_id == ctx.sid).options(ORDER_LOAD))
    if order is None or (order.user_id != ctx.user.id and not ctx.is_admin):
        raise not_found("order_not_found", "Order not found")
    return (await _serialise(session, ctx, [order], admin_view=ctx.is_admin and order.user_id != ctx.user.id))[0]


@router.post("/orders/{order_id}/approve", response_model=OrderOut)
async def approve(
    order_id: uuid.UUID, background: BackgroundTasks, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    order = await svc.lock_order(session, ctx.sid, order_id)
    await svc.approve_order(session, ctx, order, background)
    await session.flush()
    return (await _serialise(session, ctx, [order], True))[0]


@router.post("/orders/{order_id}/reject", response_model=OrderOut)
async def reject(
    order_id: uuid.UUID, body: RejectIn, background: BackgroundTasks,
    ctx: SocietyContext = Depends(require_role(Role.ADMIN)), session: AsyncSession = Depends(get_session),
):
    order = await svc.lock_order(session, ctx.sid, order_id)
    await svc.reject_order(session, ctx, order, body.reason, background)
    await session.flush()
    return (await _serialise(session, ctx, [order], True))[0]


@router.post("/orders/bulk-approve", response_model=BulkApproveOut)
async def bulk_approve(
    body: BulkApproveIn, background: BackgroundTasks, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    """Approves every listed order that is clean. Flagged orders are skipped unless `include_flagged`,
    so a one-tap 'approve all' can never wave through a duplicate UTR or amount mismatch."""
    approved, skipped = [], []
    for oid in sorted(set(body.order_ids)):
        try:
            async with session.begin_nested():
                order = await svc.lock_order(session, ctx.sid, oid)
                if order.flags and not body.include_flagged:
                    skipped.append({"id": str(oid), "reason": "flagged", "flags": list(order.flags)})
                    continue
                await svc.approve_order(session, ctx, order, background)
                approved.append(oid)
        except ApiError as e:
            skipped.append({"id": str(oid), "reason": e.detail["code"]})
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="order.bulk_approve", entity="order",
          approved=len(approved), skipped=len(skipped))
    return BulkApproveOut(approved=approved, skipped=skipped)
