import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import SocietyContext
from app.core.errors import forbidden
from app.core.security import InvalidQrToken, verify_qr_token
from app.models import Event, EventDay, Order, Pass, PassScan, PassTier, PassTierDay, User, VolunteerAssignment
from app.models.enums import EventStatus, OrderStatus, PassStatus, Role, ValidDays
from app.schemas.scan import Counters, ScanOut
from app.services.events import society_tz


async def authorize_scanner(session: AsyncSession, ctx: SocietyContext, event_id: uuid.UUID) -> None:
    """Admins/owners may scan any event of their society; volunteers only events they're assigned to, and only
    until the assignment expires (event end + grace)."""
    if ctx.is_admin:
        return
    if ctx.role != Role.VOLUNTEER:
        raise forbidden("insufficient_role", "Only volunteers and admins can scan")
    exp = await session.scalar(
        select(VolunteerAssignment.expires_at).where(
            VolunteerAssignment.event_id == event_id, VolunteerAssignment.user_id == ctx.user.id
        )
    )
    if exp is None:
        raise forbidden("not_assigned", "You are not assigned to scan this event")
    if exp <= datetime.now(UTC):
        raise forbidden("assignment_expired", "Your volunteer assignment for this event has ended")


def current_day(event: Event, days: list[EventDay], society_tz_name_tz, now: datetime) -> EventDay | None:
    """The event day we're scanning for. Uses the society's local date; an event running past midnight keeps
    counting as the previous day until it ends."""
    local = now.astimezone(society_tz_name_tz)
    by_date = {d.date: d for d in days}
    if local.date() in by_date:
        return by_date[local.date()]
    prev = local.date() - timedelta(days=1)
    if prev in by_date and now <= event.ends_at + timedelta(hours=2):
        return by_date[prev]
    return None


def _valid_on_day(day_id):
    return or_(
        PassTier.valid_days == ValidDays.ALL.value,
        exists().where(PassTierDay.tier_id == PassTier.id, PassTierDay.event_day_id == day_id),
    )


async def counters(session: AsyncSession, event_id: uuid.UUID, day: EventDay | None) -> Counters:
    sold = await session.scalar(
        select(func.count()).select_from(Pass).where(Pass.event_id == event_id, Pass.status == PassStatus.ACTIVE.value)
    )
    scanned = expected = 0
    if day is not None:
        scanned = await session.scalar(
            select(func.count()).select_from(PassScan).where(PassScan.event_day_id == day.id)
        )
        expected = await session.scalar(
            select(func.count()).select_from(Pass).join(PassTier, PassTier.id == Pass.tier_id)
            .where(Pass.event_id == event_id, Pass.status == PassStatus.ACTIVE.value, _valid_on_day(day.id))
        )
    return Counters(sold=sold, scanned_today=scanned, expected_today=expected)


async def scan_pass(
    session: AsyncSession, ctx: SocietyContext, event: Event, days: list[EventDay], token: str,
    gate: str | None, client_ref: str | None,
) -> ScanOut:
    now = datetime.now(UTC)
    day = current_day(event, days, society_tz(ctx.society), now)

    async def out(result: str, message: str, ok: bool = False, p: Pass | None = None, tier: PassTier | None = None,
                  scanned_at: datetime | None = None, scanned_by: str | None = None) -> ScanOut:
        return ScanOut(
            ok=ok, result=result, message=message, holder_name=p.holder_name if p else None,
            holder_type=p.holder_type if p else None, tier_name=tier.name if tier else None,
            pass_id=p.id if p else None, scanned_at=scanned_at, scanned_by=scanned_by,
            day=day.date if day else None, counters=await counters(session, event.id, day),
        )

    try:
        payload = verify_qr_token(token)
    except InvalidQrToken:
        return await out("invalid_token", "Not a valid SocietyPass QR code")
    # Society-scoped lookup: a genuine pass from another society is reported exactly like a forged one.
    row = (await session.execute(
        select(Pass, PassTier, Order.status).join(PassTier, PassTier.id == Pass.tier_id)
        .join(Order, Order.id == Pass.order_id)
        .where(Pass.id == payload["pass_id"], Pass.society_id == ctx.sid)
    )).first()
    if row is None or row.Pass.qr_token != token:
        return await out("invalid_token", "Not a valid SocietyPass QR code")
    p, tier, order_status = row.Pass, row.PassTier, row.status
    if p.event_id != event.id:
        other = await session.scalar(select(Event.title).where(Event.id == p.event_id))
        return await out("wrong_event", f"This pass is for “{other}”", p=p, tier=tier)
    if event.status in (EventStatus.CANCELLED, EventStatus.DRAFT):
        return await out("event_not_active", "This event is not active", p=p, tier=tier)
    if p.status != PassStatus.ACTIVE or order_status != OrderStatus.APPROVED:
        return await out("pass_revoked", "This pass has been revoked", p=p, tier=tier)
    if day is None:
        return await out("not_event_day", "Today is not a day of this event", p=p, tier=tier)
    if tier.valid_days == ValidDays.SPECIFIC:
        valid = await session.scalar(
            select(func.count()).select_from(PassTierDay).where(PassTierDay.tier_id == tier.id, PassTierDay.event_day_id == day.id)
        )
        if not valid:
            return await out("tier_not_valid_today", f"“{tier.name}” is not valid today", p=p, tier=tier)

    # One scan per pass per day, enforced by the unique constraint → race-free and idempotent.
    inserted = await session.scalar(
        pg_insert(PassScan).values(pass_id=p.id, event_day_id=day.id, scanned_by=ctx.user.id, gate=gate, client_ref=client_ref)
        .on_conflict_do_nothing(constraint="uq_scan_pass_day").returning(PassScan.id)
    )
    if inserted:
        return await out("ok", "Entry allowed", ok=True, p=p, tier=tier, scanned_at=now)
    existing, by = (await session.execute(
        select(PassScan, User.name).join(User, User.id == PassScan.scanned_by)
        .where(PassScan.pass_id == p.id, PassScan.event_day_id == day.id)
    )).one()
    if client_ref and existing.client_ref == client_ref:  # the same request retried (flaky network) → same answer
        return await out("ok", "Entry allowed", ok=True, p=p, tier=tier, scanned_at=existing.scanned_at)
    return await out("already_scanned", "Already scanned today", p=p, tier=tier, scanned_at=existing.scanned_at, scanned_by=by)


async def day_stats(session: AsyncSession, event_id: uuid.UUID, days: list[EventDay]):
    scanned = dict((await session.execute(
        select(PassScan.event_day_id, func.count()).join(EventDay, EventDay.id == PassScan.event_day_id)
        .where(EventDay.event_id == event_id).group_by(PassScan.event_day_id)
    )).all())
    expected = dict((await session.execute(
        select(EventDay.id, func.count(Pass.id))
        .select_from(EventDay)
        .join(Pass, and_(Pass.event_id == EventDay.event_id, Pass.status == PassStatus.ACTIVE.value))
        .join(PassTier, PassTier.id == Pass.tier_id)
        .where(EventDay.event_id == event_id, _valid_on_day(EventDay.id)).group_by(EventDay.id)
    )).all())
    return [{"day_id": d.id, "date": d.date, "label": d.label, "scanned": scanned.get(d.id, 0), "expected": expected.get(d.id, 0)}
            for d in days]


def today_date(society_tz_obj, now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(society_tz_obj).date()


