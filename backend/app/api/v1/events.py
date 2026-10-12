import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_session
from app.core.deps import SocietyContext, require_role
from app.core.errors import bad_request, conflict, not_found
from app.models import (
    Event,
    EventDay,
    Membership,
    Order,
    OrderItem,
    Pass,
    PassScan,
    PassTier,
    PassTierDay,
    User,
    VolunteerAssignment,
)
from app.models.enums import EventStatus, MembershipStatus, OrderStatus, Role, UploadPurpose, ValidDays
from app.schemas.common import Msg, Page, PageParams
from app.schemas.events import (
    DayIn,
    DayOut,
    EventCreate,
    EventOut,
    EventUpdate,
    TierIn,
    TierOut,
    TierUpdate,
    VolunteerIn,
    VolunteerOut,
)
from app.services.audit import audit
from app.services.events import (
    VOLUNTEER_GRACE,
    default_days,
    events_out,
    load_event,
    society_tz,
    tier_usage,
    validate_tier_days,
)
from app.services.payments import get_provider
from app.services.push import push
from app.services.uploads import consume_image_upload

router = APIRouter(prefix="/societies/{society_id}/events", tags=["events"])


def _editable(ev: Event) -> None:
    if ev.status == EventStatus.CANCELLED:
        raise conflict("event_cancelled", "Cancelled events can't be edited")


async def _one(session: AsyncSession, ev: Event) -> EventOut:
    return (await events_out(session, [ev]))[0]


def _make_tier(ev: Event, body: TierIn, days: list[EventDay]) -> PassTier:
    if body.price > 0 and not ev.is_paid:
        raise bad_request("free_event_price", "This event is marked free; tiers must have price 0")
    tier = PassTier(
        event_id=ev.id, name=body.name.strip(), description=body.description, price=body.price,
        capacity=body.capacity, per_user_limit=body.per_user_limit, valid_days=body.valid_days.value,
        allow_guests=body.allow_guests, sort_order=body.sort_order,
    )
    if body.valid_days == ValidDays.SPECIFIC:
        tier.day_links = [PassTierDay(event_day_id=d.id) for d in validate_tier_days(body.day_dates, days)]
    return tier


@router.post("", response_model=EventOut, status_code=201)
async def create_event(
    body: EventCreate, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    try:
        get_provider(body.payment_provider)
    except ValueError as e:
        raise bad_request("invalid_payment_provider", str(e)) from e
    ev = Event(
        society_id=ctx.sid, title=body.title.strip(), description=body.description, venue=body.venue,
        starts_at=body.starts_at, ends_at=body.ends_at, booking_deadline=body.booking_deadline,
        is_paid=body.is_paid, payment_provider=body.payment_provider, created_by=ctx.user.id,
        status=EventStatus.DRAFT.value,
    )
    session.add(ev)
    if body.days:
        dates = {d.date: d.label for d in body.days}
    else:
        dates = {d: None for d in default_days(body.starts_at, body.ends_at, society_tz(ctx.society))}
    if len(dates) > 31:
        raise bad_request("event_too_long", "Events can span at most 31 days")
    ev.days = [EventDay(id=uuid.uuid4(), date=d, label=lbl) for d, lbl in sorted(dates.items())]
    ev.tiers = [_make_tier(ev, t, ev.days) for t in body.tiers]
    if body.banner_upload_id:
        ev.banner_key, _, _ = await consume_image_upload(
            session, body.banner_upload_id, ctx.user, ctx.sid, UploadPurpose.BANNER, max_side=1600
        )
    await session.flush()
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="event.create", entity="event",
          entity_id=ev.id, title=ev.title)
    ev = await load_event(session, ctx.sid, ev.id)
    return await _one(session, ev)


@router.get("", response_model=Page[EventOut])
async def list_events(
    when: Literal["upcoming", "past", "all"] = Query("all"),
    status: EventStatus | None = Query(None),
    page: PageParams = Depends(),
    ctx: SocietyContext = Depends(require_role(Role.MEMBER)),
    session: AsyncSession = Depends(get_session),
):
    conds = [Event.society_id == ctx.sid]
    if not ctx.is_admin:
        conds.append(Event.status != EventStatus.DRAFT.value)  # drafts are admin-only
    if status:
        conds.append(Event.status == status.value)
    now = datetime.now(UTC)
    if when == "upcoming":
        conds.append(Event.ends_at >= now)
    elif when == "past":
        conds.append(Event.ends_at < now)
    total = await session.scalar(select(func.count()).select_from(Event).where(*conds))
    order = Event.starts_at.desc() if when == "past" else Event.starts_at.asc()
    events = (await session.scalars(
        select(Event).where(*conds).order_by(order).limit(page.limit).offset(page.offset)
        .options(selectinload(Event.days), selectinload(Event.tiers).selectinload(PassTier.day_links))
    )).all()
    return Page(items=await events_out(session, list(events)), total=total, limit=page.limit, offset=page.offset)


@router.get("/{event_id}", response_model=EventOut)
async def get_event(
    event_id: uuid.UUID, ctx: SocietyContext = Depends(require_role(Role.MEMBER)),
    session: AsyncSession = Depends(get_session),
):
    ev = await load_event(session, ctx.sid, event_id)
    if ev.status == EventStatus.DRAFT and not ctx.is_admin:
        raise not_found("event_not_found", "Event not found")
    return await _one(session, ev)


@router.patch("/{event_id}", response_model=EventOut)
async def update_event(
    event_id: uuid.UUID, body: EventUpdate, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    ev = await load_event(session, ctx.sid, event_id, lock=True)
    _editable(ev)
    for f in ("title", "description", "venue", "starts_at", "ends_at", "booking_deadline"):
        v = getattr(body, f)
        if v is not None:
            setattr(ev, f, v.strip() if isinstance(v, str) else v)
    if body.clear_booking_deadline:
        ev.booking_deadline = None
    if ev.ends_at < ev.starts_at:
        raise bad_request("invalid_times", "ends_at must be after starts_at")
    if body.ends_at:  # volunteers' scan rights follow the event end
        await session.execute(
            update(VolunteerAssignment).where(VolunteerAssignment.event_id == ev.id)
            .values(expires_at=ev.ends_at + VOLUNTEER_GRACE)
        )
        ev.reminder_sent_at = None if body.starts_at else ev.reminder_sent_at
    if body.banner_upload_id:
        ev.banner_key, _, _ = await consume_image_upload(
            session, body.banner_upload_id, ctx.user, ctx.sid, UploadPurpose.BANNER, max_side=1600
        )
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="event.update", entity="event", entity_id=ev.id)
    await session.flush()
    session.expire(ev)
    return await _one(session, await load_event(session, ctx.sid, event_id))


@router.post("/{event_id}/publish", response_model=EventOut)
async def publish_event(
    event_id: uuid.UUID, background: BackgroundTasks, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    ev = await load_event(session, ctx.sid, event_id, lock=True)
    if ev.status != EventStatus.DRAFT:
        raise conflict("not_draft", "Only draft events can be published")
    if not ev.tiers:
        raise bad_request("no_tiers", "Add at least one pass tier before publishing")
    if not ev.days:
        raise bad_request("no_days", "Add at least one event day before publishing")
    if any(t.price > 0 for t in ev.tiers) and not ctx.society.upi_id:
        raise bad_request("upi_not_configured", "Set the society's UPI ID before publishing a paid event")
    if ev.ends_at < datetime.now(UTC):
        raise bad_request("event_in_past", "This event has already ended")
    ev.status = EventStatus.PUBLISHED.value
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="event.publish", entity="event", entity_id=ev.id)
    member_ids = list((await session.scalars(
        select(Membership.user_id).where(Membership.society_id == ctx.sid,
                                         Membership.status == MembershipStatus.ACTIVE.value,
                                         Membership.user_id != ctx.user.id)
    )).all())
    background.add_task(push.send, member_ids, f"New event: {ev.title}", "Passes are now open — tap to book.",
                        {"type": "event_published", "society_id": str(ctx.sid), "event_id": str(ev.id)})
    await session.flush()
    return await _one(session, ev)


@router.post("/{event_id}/close", response_model=EventOut)
async def close_event(
    event_id: uuid.UUID, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    ev = await load_event(session, ctx.sid, event_id, lock=True)
    if ev.status != EventStatus.PUBLISHED:
        raise conflict("not_published", "Only published events can be closed")
    ev.status = EventStatus.CLOSED.value
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="event.close", entity="event", entity_id=ev.id)
    return await _one(session, ev)


@router.post("/{event_id}/reopen", response_model=EventOut)
async def reopen_event(
    event_id: uuid.UUID, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    ev = await load_event(session, ctx.sid, event_id, lock=True)
    if ev.status != EventStatus.CLOSED:
        raise conflict("not_closed", "Only closed events can be reopened")
    ev.status = EventStatus.PUBLISHED.value
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="event.reopen", entity="event", entity_id=ev.id)
    return await _one(session, ev)


@router.post("/{event_id}/cancel", response_model=EventOut)
async def cancel_event(
    event_id: uuid.UUID, background: BackgroundTasks, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    ev = await load_event(session, ctx.sid, event_id, lock=True)
    if ev.status == EventStatus.CANCELLED:
        raise conflict("already_cancelled", "Event already cancelled")
    was_draft = ev.status == EventStatus.DRAFT
    ev.status = EventStatus.CANCELLED.value
    # pending orders can no longer be fulfilled → release them; approved orders need a manual refund by the admin
    cancelled = (await session.execute(
        update(Order).where(Order.event_id == ev.id, Order.status == OrderStatus.PENDING.value)
        .values(status=OrderStatus.CANCELLED.value, reject_reason="event_cancelled").returning(Order.user_id)
    )).scalars().all()
    holders = list((await session.scalars(select(Pass.user_id).where(Pass.event_id == ev.id).distinct())).all())
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="event.cancel", entity="event", entity_id=ev.id,
          cancelled_pending_orders=len(cancelled))
    if not was_draft:
        background.add_task(push.send, list(set(holders) | set(cancelled)), f"Cancelled: {ev.title}",
                            "This event was cancelled. Contact your society admins about refunds.",
                            {"type": "event_cancelled", "society_id": str(ctx.sid), "event_id": str(ev.id)})
    return await _one(session, ev)


@router.delete("/{event_id}", response_model=Msg)
async def delete_event(
    event_id: uuid.UUID, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    ev = await load_event(session, ctx.sid, event_id, lock=True)
    has_orders = await session.scalar(
        select(func.count()).select_from(Order).where(Order.event_id == ev.id, Order.status != OrderStatus.CANCELLED.value)
    )
    if has_orders:
        raise conflict("event_has_orders", "Events with orders can't be deleted — cancel it instead")
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="event.delete", entity="event", entity_id=ev.id,
          title=ev.title)
    await session.execute(delete(Order).where(Order.event_id == ev.id))  # only cancelled ones remain
    await session.delete(ev)
    return Msg(message="Event deleted")


# ------------------------------------------------------------------------------------------- days
@router.post("/{event_id}/days", response_model=DayOut, status_code=201)
async def add_day(
    event_id: uuid.UUID, body: DayIn, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    ev = await load_event(session, ctx.sid, event_id, lock=True)
    _editable(ev)
    if any(d.date == body.date for d in ev.days):
        raise conflict("day_exists", "That day already exists")
    if len(ev.days) >= 31:
        raise bad_request("event_too_long", "Events can span at most 31 days")
    day = EventDay(event_id=ev.id, date=body.date, label=body.label)
    session.add(day)
    await session.flush()
    return DayOut(id=day.id, date=day.date, label=day.label)


@router.delete("/{event_id}/days/{day_id}", response_model=Msg)
async def remove_day(
    event_id: uuid.UUID, day_id: uuid.UUID, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    ev = await load_event(session, ctx.sid, event_id, lock=True)
    _editable(ev)
    day = next((d for d in ev.days if d.id == day_id), None)
    if day is None:
        raise not_found("day_not_found", "Day not found")
    if await session.scalar(select(func.count()).select_from(PassScan).where(PassScan.event_day_id == day.id)):
        raise conflict("day_has_scans", "This day already has scans")
    if ev.status != EventStatus.DRAFT and len(ev.days) == 1:
        raise bad_request("last_day", "A published event needs at least one day")
    await session.delete(day)
    return Msg()


# ------------------------------------------------------------------------------------------- tiers
@router.post("/{event_id}/tiers", response_model=TierOut, status_code=201)
async def add_tier(
    event_id: uuid.UUID, body: TierIn, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    ev = await load_event(session, ctx.sid, event_id, lock=True)
    _editable(ev)
    tier = _make_tier(ev, body, ev.days)
    ev.tiers.append(tier)
    await session.flush()
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="tier.create", entity="tier", entity_id=tier.id,
          event_id=ev.id, price=tier.price)
    return _find_tier(await _one(session, await load_event(session, ctx.sid, event_id)), tier.id)


def _find_tier(out: EventOut, tier_id: uuid.UUID) -> TierOut:
    return next(t for t in out.tiers if t.id == tier_id)


@router.patch("/{event_id}/tiers/{tier_id}", response_model=TierOut)
async def update_tier(
    event_id: uuid.UUID, tier_id: uuid.UUID, body: TierUpdate,
    ctx: SocietyContext = Depends(require_role(Role.ADMIN)), session: AsyncSession = Depends(get_session),
):
    ev = await load_event(session, ctx.sid, event_id, lock=True)
    _editable(ev)
    tier = next((t for t in ev.tiers if t.id == tier_id), None)
    if tier is None:
        raise not_found("tier_not_found", "Tier not found")
    usage = (await tier_usage(session, [tier.id]))[tier.id]
    if body.capacity is not None and body.capacity < usage["approved"] + usage["pending"]:
        raise conflict("capacity_below_reserved", "Capacity can't be lower than passes already sold or reserved",
                       reserved=usage["approved"] + usage["pending"])
    if body.price is not None and body.price > 0 and not ev.is_paid:
        raise bad_request("free_event_price", "This event is marked free")
    if body.price is not None and body.price != tier.price:
        audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="tier.price_change", entity="tier",
              entity_id=tier.id, old=tier.price, new=body.price)
    for f in ("name", "description", "price", "capacity", "per_user_limit", "allow_guests", "sort_order"):
        v = getattr(body, f)
        if v is not None:
            setattr(tier, f, v)
    if body.valid_days is not None:
        tier.valid_days = body.valid_days.value
        if body.valid_days == ValidDays.ALL:
            tier.day_links = []
    if body.day_dates is not None:
        if (body.valid_days or ValidDays(tier.valid_days)) != ValidDays.SPECIFIC or not body.day_dates:
            raise bad_request("invalid_tier_days", "day_dates requires valid_days='specific' and ≥1 date")
        tier.day_links = [PassTierDay(tier_id=tier.id, event_day_id=d.id) for d in validate_tier_days(body.day_dates, ev.days)]
    elif body.valid_days == ValidDays.SPECIFIC and not tier.day_links:
        raise bad_request("invalid_tier_days", "Provide day_dates for a 'specific' tier")
    await session.flush()
    return _find_tier(await _one(session, await load_event(session, ctx.sid, event_id)), tier_id)


@router.delete("/{event_id}/tiers/{tier_id}", response_model=Msg)
async def delete_tier(
    event_id: uuid.UUID, tier_id: uuid.UUID, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    ev = await load_event(session, ctx.sid, event_id, lock=True)
    tier = next((t for t in ev.tiers if t.id == tier_id), None)
    if tier is None:
        raise not_found("tier_not_found", "Tier not found")
    if await session.scalar(select(func.count()).select_from(OrderItem).where(OrderItem.tier_id == tier.id)):
        raise conflict("tier_has_orders", "This tier already has orders; set its capacity to 0 instead")
    await session.delete(tier)
    return Msg()


# ------------------------------------------------------------------------------------------- volunteers
@router.get("/{event_id}/volunteers", response_model=list[VolunteerOut])
async def list_volunteers(
    event_id: uuid.UUID, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    await load_event(session, ctx.sid, event_id)
    now = datetime.now(UTC)
    rows = (await session.execute(
        select(VolunteerAssignment, User).join(User, User.id == VolunteerAssignment.user_id)
        .where(VolunteerAssignment.event_id == event_id).order_by(User.name)
    )).all()
    return [VolunteerOut(user_id=u.id, name=u.name, phone=u.phone, expires_at=a.expires_at, active=a.expires_at > now)
            for a, u in rows]


@router.post("/{event_id}/volunteers", response_model=VolunteerOut, status_code=201)
async def assign_volunteer(
    event_id: uuid.UUID, body: VolunteerIn, background: BackgroundTasks,
    ctx: SocietyContext = Depends(require_role(Role.ADMIN)), session: AsyncSession = Depends(get_session),
):
    ev = await load_event(session, ctx.sid, event_id)
    _editable(ev)
    m = await session.scalar(
        select(Membership).where(Membership.society_id == ctx.sid, Membership.user_id == body.user_id,
                                 Membership.status == MembershipStatus.ACTIVE.value).with_for_update()
    )
    if m is None:
        raise not_found("member_not_found", "That person is not an active member of this society")
    if m.role == Role.MEMBER.value:
        m.role = Role.VOLUNTEER.value
        audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="member.role_change", entity="membership",
              entity_id=m.id, user_id=body.user_id, from_role="member", to_role="volunteer", via="volunteer_assignment")
    expires = ev.ends_at + VOLUNTEER_GRACE
    existing = await session.scalar(
        select(VolunteerAssignment).where(VolunteerAssignment.event_id == ev.id, VolunteerAssignment.user_id == body.user_id)
    )
    if existing:
        existing.expires_at = expires
    else:
        session.add(VolunteerAssignment(event_id=ev.id, user_id=body.user_id, expires_at=expires))
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="volunteer.assign", entity="event",
          entity_id=ev.id, user_id=body.user_id)
    user = await session.get(User, body.user_id)
    background.add_task(push.send, [body.user_id], "Volunteer duty", f"You're a gate volunteer for {ev.title}",
                        {"type": "volunteer_assigned", "society_id": str(ctx.sid), "event_id": str(ev.id)})
    return VolunteerOut(user_id=user.id, name=user.name, phone=user.phone, expires_at=expires, active=True)


@router.delete("/{event_id}/volunteers/{user_id}", response_model=Msg)
async def remove_volunteer(
    event_id: uuid.UUID, user_id: uuid.UUID, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    await load_event(session, ctx.sid, event_id)
    await session.execute(delete(VolunteerAssignment).where(
        VolunteerAssignment.event_id == event_id, VolunteerAssignment.user_id == user_id))
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="volunteer.remove", entity="event",
          entity_id=event_id, user_id=user_id)
    return Msg()
