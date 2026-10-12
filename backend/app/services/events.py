import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.errors import bad_request, not_found
from app.models import Event, EventDay, Order, OrderItem, PassTier, Society
from app.models.enums import EventStatus, OrderStatus, ValidDays
from app.schemas.events import DayOut, EventOut, TierOut
from app.services.storage import get_storage

VOLUNTEER_GRACE = timedelta(hours=6)  # assignment lives a little past the scheduled end (late finishes)


def society_tz(society: Society) -> ZoneInfo:
    return ZoneInfo(society.timezone or "Asia/Kolkata")


def default_days(starts_at: datetime, ends_at: datetime, tz: ZoneInfo) -> list[date]:
    start, end = starts_at.astimezone(tz).date(), ends_at.astimezone(tz).date()
    n = (end - start).days + 1
    if n > 31:
        raise bad_request("event_too_long", "Events can span at most 31 days")
    return [start + timedelta(days=i) for i in range(n)]


async def load_event(session: AsyncSession, society_id: uuid.UUID, event_id: uuid.UUID, *, lock: bool = False) -> Event:
    """Always scoped by society_id — a foreign event id is indistinguishable from a missing one."""
    q = (
        select(Event)
        .where(Event.id == event_id, Event.society_id == society_id)
        .options(selectinload(Event.days), selectinload(Event.tiers).selectinload(PassTier.day_links))
    )
    if lock:
        q = q.with_for_update(of=Event)
    ev = await session.scalar(q)
    if ev is None:
        raise not_found("event_not_found", "Event not found")
    return ev


def live_order_filter():
    """Orders that currently hold capacity: approved; pending with payment proof submitted (waiting on an admin —
    never expires on the member); or pending without proof and younger than the TTL."""
    cutoff = datetime.now(UTC) - timedelta(hours=get_settings().pending_order_ttl_hours)
    return or_(
        Order.status == OrderStatus.APPROVED.value,
        and_(
            Order.status == OrderStatus.PENDING.value,
            or_(Order.payment_submitted_at.is_not(None), Order.created_at > cutoff),
        ),
    )


async def tier_usage(session: AsyncSession, tier_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
    usage = {t: {"approved": 0, "pending": 0} for t in tier_ids}
    if not tier_ids:
        return usage
    rows = await session.execute(
        select(OrderItem.tier_id, Order.status, func.coalesce(func.sum(OrderItem.qty), 0))
        .join(Order, Order.id == OrderItem.order_id)
        .where(OrderItem.tier_id.in_(tier_ids), live_order_filter())
        .group_by(OrderItem.tier_id, Order.status)
    )
    for tier_id, status, qty in rows:
        usage[tier_id]["approved" if status == OrderStatus.APPROVED.value else "pending"] += int(qty)
    return usage


async def events_out(session: AsyncSession, events: list[Event]) -> list[EventOut]:
    """Batch-serialise (one usage query for all tiers → no N+1)."""
    tier_ids = [t.id for e in events for t in e.tiers]
    usage = await tier_usage(session, tier_ids)
    storage = get_storage()
    now = datetime.now(UTC)
    out = []
    for e in events:
        tiers = []
        for t in sorted(e.tiers, key=lambda t: (t.sort_order, t.price)):
            u = usage[t.id]
            tiers.append(TierOut(
                id=t.id, name=t.name, description=t.description, price=t.price, capacity=t.capacity,
                per_user_limit=t.per_user_limit, valid_days=ValidDays(t.valid_days),
                day_ids=[link.event_day_id for link in t.day_links], allow_guests=t.allow_guests,
                sort_order=t.sort_order, sold=u["approved"], pending=u["pending"],
                remaining=max(t.capacity - u["approved"] - u["pending"], 0),
            ))
        is_over = e.ends_at < now
        out.append(EventOut(
            id=e.id, society_id=e.society_id, title=e.title, description=e.description, venue=e.venue,
            starts_at=e.starts_at, ends_at=e.ends_at, banner_url=storage.url_for(e.banner_key),
            booking_deadline=e.booking_deadline, status=EventStatus(e.status), is_paid=e.is_paid,
            payment_provider=e.payment_provider, days=[DayOut(id=d.id, date=d.date, label=d.label) for d in e.days],
            tiers=tiers, is_over=is_over, created_at=e.created_at,
            booking_open=(e.status == EventStatus.PUBLISHED and not is_over
                          and (e.booking_deadline is None or e.booking_deadline > now)),
        ))
    return out


def validate_tier_days(tier_day_dates: list[date], days: list[EventDay]) -> list[EventDay]:
    by_date = {d.date: d for d in days}
    missing = [d.isoformat() for d in tier_day_dates if d not in by_date]
    if missing:
        raise bad_request("invalid_tier_days", f"Tier days not in event: {', '.join(missing)}")
    return [by_date[d] for d in tier_day_dates]
