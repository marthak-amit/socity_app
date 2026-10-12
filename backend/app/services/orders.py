import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.deps import SocietyContext
from app.core.errors import bad_request, conflict, not_found
from app.core.security import make_qr_token, random_code
from app.models import Event, Membership, Order, OrderItem, Pass, PassTier, User
from app.models.enums import EventStatus, HolderType, OrderFlag, OrderStatus, PassStatus
from app.schemas.orders import (
    OrderCreate,
    OrderItemOut,
    OrderMemberOut,
    OrderOut,
    PaymentInstructionsOut,
    PaymentSubmit,
)
from app.services.audit import audit
from app.services.events import live_order_filter, load_event, tier_usage
from app.services.payments import get_provider
from app.services.push import push
from app.services.storage import get_storage


def ttl() -> timedelta:
    return timedelta(hours=get_settings().pending_order_ttl_hours)


def is_unpaid_expired(order: Order, now: datetime | None = None) -> bool:
    return (
        order.status == OrderStatus.PENDING and order.payment_submitted_at is None
        and order.created_at <= (now or datetime.now(UTC)) - ttl()
    )


# --------------------------------------------------------------------------------------------- creation
def _normalise_holders(item_qty: int, holders, tier: PassTier, buyer_name: str) -> list[dict]:
    if holders and len(holders) != item_qty:
        raise bad_request("holder_count_mismatch", f"Provide exactly {item_qty} holder name(s) for '{tier.name}'")
    result = []
    for i in range(item_qty):
        if holders:
            h = holders[i]
            name, htype = h.name.strip(), h.type
        else:
            name, htype = (buyer_name, HolderType.MEMBER) if i == 0 else (f"{buyer_name} +{i}", HolderType.MEMBER)
        if not name:
            raise bad_request("holder_name_required", "Every pass needs a holder name")
        if htype == HolderType.GUEST and not tier.allow_guests:
            raise bad_request("guests_not_allowed", f"'{tier.name}' passes can't be issued to guests")
        result.append({"name": name, "type": htype.value})
    return result


async def create_order(session: AsyncSession, ctx: SocietyContext, event_id: uuid.UUID, body: OrderCreate) -> Order:
    ev = await load_event(session, ctx.sid, event_id)
    now = datetime.now(UTC)
    if ev.status != EventStatus.PUBLISHED or ev.ends_at < now or (ev.booking_deadline and ev.booking_deadline < now):
        raise conflict("booking_closed", "Booking is closed for this event")
    tier_ids = [i.tier_id for i in body.items]
    if len(set(tier_ids)) != len(tier_ids):
        raise bad_request("duplicate_tier", "Each tier may appear only once per order")
    tiers = {t.id: t for t in ev.tiers}
    if any(t not in tiers for t in tier_ids):
        raise not_found("tier_not_found", "Tier not found for this event")

    # Serialise concurrent buyers of the same tiers (deterministic order → no deadlocks).
    await session.execute(select(PassTier.id).where(PassTier.id.in_(tier_ids)).order_by(PassTier.id).with_for_update())
    usage = await tier_usage(session, tier_ids)
    mine = dict((await session.execute(
        select(OrderItem.tier_id, func.coalesce(func.sum(OrderItem.qty), 0))
        .join(Order, Order.id == OrderItem.order_id)
        .where(OrderItem.tier_id.in_(tier_ids), Order.user_id == ctx.user.id, live_order_filter())
        .group_by(OrderItem.tier_id)
    )).all())

    buyer = ctx.user.name or ctx.user.phone
    items, total = [], 0
    for it in body.items:
        t = tiers[it.tier_id]
        remaining = t.capacity - usage[t.id]["approved"] - usage[t.id]["pending"]
        if it.qty > remaining:
            raise conflict("sold_out" if remaining <= 0 else "insufficient_capacity",
                           f"Only {max(remaining, 0)} pass(es) left for '{t.name}'", tier_id=str(t.id), remaining=max(remaining, 0))
        if int(mine.get(t.id, 0)) + it.qty > t.per_user_limit:
            raise conflict("per_user_limit_exceeded", f"You can hold at most {t.per_user_limit} '{t.name}' pass(es)",
                           tier_id=str(t.id), limit=t.per_user_limit)
        unit = t.price if ev.is_paid else 0
        total += unit * it.qty
        items.append(OrderItem(tier_id=t.id, qty=it.qty, unit_price=unit,
                               holders=_normalise_holders(it.qty, it.holders, t, buyer)))
    if total > 0 and not ctx.society.upi_id:
        raise bad_request("upi_not_configured", "This society hasn't set up its UPI ID yet")

    order = Order(
        ref_code=f"SP-{random_code(8)}", event_id=ev.id, user_id=ctx.user.id, society_id=ctx.sid, total_amount=total,
        payment_provider=ev.payment_provider, status=OrderStatus.PENDING.value, flags=[], items=items,
    )
    session.add(order)
    await session.flush()
    if total == 0:  # free pass: nothing to review
        await _issue_passes(session, order, ev)
        order.status = OrderStatus.APPROVED.value
        order.reviewed_at = now
        audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="order.auto_approve", entity="order",
              entity_id=order.id, reason="free")
    return order


# --------------------------------------------------------------------------------------------- payment proof
async def submit_payment(session: AsyncSession, ctx: SocietyContext, order: Order, body: PaymentSubmit) -> Order:
    from app.models.enums import UploadPurpose
    from app.services.uploads import consume_image_upload

    if order.status != OrderStatus.PENDING:
        raise conflict("not_pending", "This order can no longer be changed")
    if is_unpaid_expired(order):
        raise conflict("order_expired", "This order expired — please place a new one")
    if order.total_amount == 0:
        raise conflict("no_payment_needed", "This order is free")
    if body.screenshot_upload_id is None and body.utr is None and not order.screenshot_key and not order.utr:
        raise bad_request("proof_required", "Upload a payment screenshot and/or enter the UTR number")
    storage = get_storage()
    if body.screenshot_upload_id:
        old = order.screenshot_key
        order.screenshot_key, _, _ = await consume_image_upload(
            session, body.screenshot_upload_id, ctx.user, ctx.sid, UploadPurpose.SCREENSHOT, max_side=2200
        )
        if old:
            await storage.delete_object(old)
    if body.utr:
        order.utr = body.utr
    if body.paid_amount is not None:
        order.paid_amount = body.paid_amount
    order.payment_submitted_at = datetime.now(UTC)
    await compute_flags(session, order)
    return order


async def compute_flags(session: AsyncSession, order: Order) -> None:
    flags: set[str] = set()
    if not order.utr:
        flags.add(OrderFlag.MISSING_UTR.value)
    if order.paid_amount is not None and order.paid_amount != order.total_amount:
        flags.add(OrderFlag.AMOUNT_MISMATCH.value)
    if order.utr:
        dupes = (await session.scalars(
            select(Order).where(Order.utr == order.utr, Order.id != order.id).with_for_update()
        )).all()
        if dupes:
            flags.add(OrderFlag.DUPLICATE_UTR.value)
            for d in dupes:  # flag the earlier orders too, so reviewers of either see it
                if OrderFlag.DUPLICATE_UTR.value not in d.flags:
                    d.flags = [*d.flags, OrderFlag.DUPLICATE_UTR.value]
    order.flags = sorted(flags)


# --------------------------------------------------------------------------------------------- review
async def lock_order(session: AsyncSession, society_id: uuid.UUID, order_id: uuid.UUID) -> Order:
    order = await session.scalar(
        select(Order).where(Order.id == order_id, Order.society_id == society_id)
        .options(selectinload(Order.items).selectinload(OrderItem.tier)).with_for_update(of=Order)
    )
    if order is None:
        raise not_found("order_not_found", "Order not found")
    return order


async def _issue_passes(session: AsyncSession, order: Order, ev: Event) -> list[Pass]:
    passes = []
    for item in order.items:
        for h in item.holders:
            pid = uuid.uuid4()
            passes.append(Pass(
                id=pid, order_id=order.id, tier_id=item.tier_id, event_id=ev.id, society_id=order.society_id,
                user_id=order.user_id, holder_name=h["name"], holder_type=h["type"],
                qr_token=make_qr_token(pid, ev.id), status=PassStatus.ACTIVE.value,
            ))
    session.add_all(passes)
    return passes


async def approve_order(session: AsyncSession, ctx: SocietyContext, order: Order, background) -> list[Pass]:
    if order.status != OrderStatus.PENDING:
        raise conflict("not_pending", f"Order is already {order.status}")
    if order.total_amount > 0 and order.payment_submitted_at is None:
        raise conflict("payment_not_submitted", "The member hasn't submitted payment proof yet")
    ev = await session.get(Event, order.event_id)
    if ev.status == EventStatus.CANCELLED:
        raise conflict("event_cancelled", "This event was cancelled")
    if is_unpaid_expired(order):  # (defensive) seats may have been re-sold
        usage = await tier_usage(session, [i.tier_id for i in order.items])
        for i in order.items:
            if i.qty > i.tier.capacity - usage[i.tier_id]["approved"] - usage[i.tier_id]["pending"]:
                raise conflict("capacity_exceeded", f"'{i.tier.name}' is sold out")
    passes = await _issue_passes(session, order, ev)
    order.status = OrderStatus.APPROVED.value
    order.reviewed_by, order.reviewed_at, order.reject_reason = ctx.user.id, datetime.now(UTC), None
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="order.approve", entity="order", entity_id=order.id,
          amount=order.total_amount, flags=order.flags, utr=order.utr)
    background.add_task(
        push.send, [order.user_id], "Your pass is ready 🎟️", f"Payment approved for {ev.title}. Tap to view your pass.",
        {"type": "order_approved", "society_id": str(ctx.sid), "order_id": str(order.id), "event_id": str(ev.id)},
    )
    return passes


async def reject_order(session: AsyncSession, ctx: SocietyContext, order: Order, reason: str, background) -> None:
    if order.status != OrderStatus.PENDING:
        raise conflict("not_pending", f"Order is already {order.status}")
    order.status = OrderStatus.REJECTED.value
    order.reject_reason = reason.strip()
    order.reviewed_by, order.reviewed_at = ctx.user.id, datetime.now(UTC)
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="order.reject", entity="order", entity_id=order.id,
          reason=order.reject_reason, amount=order.total_amount, utr=order.utr)
    background.add_task(
        push.send, [order.user_id], "Payment not approved", f"{order.reject_reason}",
        {"type": "order_rejected", "society_id": str(ctx.sid), "order_id": str(order.id)},
    )


async def cancel_order(session: AsyncSession, ctx: SocietyContext, order: Order) -> None:
    if order.status != OrderStatus.PENDING:
        raise conflict("not_pending", "Only pending orders can be cancelled")
    order.status = OrderStatus.CANCELLED.value
    order.reject_reason = "cancelled_by_member" if order.user_id == ctx.user.id else "cancelled_by_admin"
    if order.user_id != ctx.user.id:
        audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="order.cancel", entity="order", entity_id=order.id)


async def expire_pending_orders() -> int:
    """Release seats held by orders that never got payment proof within the TTL."""
    cutoff = datetime.now(UTC) - ttl()
    async with SessionLocal() as session:
        rows = (await session.execute(
            update(Order)
            .where(Order.status == OrderStatus.PENDING.value, Order.payment_submitted_at.is_(None),
                   Order.created_at <= cutoff, Order.total_amount > 0)
            .values(status=OrderStatus.CANCELLED.value, reject_reason="expired")
            .returning(Order.id, Order.user_id, Order.society_id)
        )).all()
        for oid, _, sid in rows:
            audit(session, society_id=sid, actor_id=None, action="order.expire", entity="order", entity_id=oid)
        await session.commit()
    for _, uid, _ in rows:
        await push.send([uid], "Order expired", "Your pass order expired because no payment was submitted.",
                        {"type": "order_expired"})
    return len(rows)


# --------------------------------------------------------------------------------------------- serialisation
async def orders_out(
    session: AsyncSession, orders: list[Order], *, ctx: SocietyContext, admin_view: bool,
    members: dict[uuid.UUID, tuple[User, Membership | None]] | None = None,
) -> list[OrderOut]:
    """Batch-serialise. `admin_view` exposes flags, screenshot URL and buyer identity; buyers only see their own."""
    storage = get_storage()
    event_titles = {}
    ev_ids = {o.event_id for o in orders}
    if ev_ids:
        event_titles = dict((await session.execute(select(Event.id, Event.title).where(Event.id.in_(ev_ids)))).all())
    out = []
    for o in orders:
        payment = None
        if not admin_view and o.status == OrderStatus.PENDING and o.total_amount > 0 and o.user_id == ctx.user.id:
            pi = get_provider(o.payment_provider).instructions(o, ctx.society)
            payment = PaymentInstructionsOut(**pi.__dict__)
        member = None
        if admin_view and members and o.user_id in members:
            u, m = members[o.user_id]
            member = OrderMemberOut(user_id=u.id, name=u.name, phone=u.phone,
                                    wing=m.wing if m else None, flat_no=m.flat_no if m else None)
        out.append(OrderOut(
            id=o.id, ref_code=o.ref_code, event_id=o.event_id, event_title=event_titles.get(o.event_id, ""),
            society_id=o.society_id, status=OrderStatus(o.status), total_amount=o.total_amount,
            paid_amount=o.paid_amount, utr=o.utr, has_screenshot=bool(o.screenshot_key),
            screenshot_url=await storage.presigned_get(o.screenshot_key) if (admin_view and o.screenshot_key) else None,
            payment_submitted_at=o.payment_submitted_at, flags=list(o.flags) if admin_view else [],
            reject_reason=o.reject_reason, reviewed_at=o.reviewed_at, created_at=o.created_at,
            expires_at=(o.created_at + ttl()) if (o.status == OrderStatus.PENDING and o.payment_submitted_at is None
                                                    and o.total_amount > 0) else None,
            items=[OrderItemOut(tier_id=i.tier_id, tier_name=i.tier.name, qty=i.qty, unit_price=i.unit_price,
                                holders=i.holders) for i in o.items],
            payment=payment, member=member,
        ))
    return out


