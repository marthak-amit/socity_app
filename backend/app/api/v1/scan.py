import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import SocietyContext, require_role
from app.models import Event, EventDay, Pass, PassScan, PassTier, User, VolunteerAssignment
from app.models.enums import EventStatus, PassStatus, Role
from app.schemas.common import Page, PageParams
from app.schemas.scan import (
    DayStat,
    RecentScan,
    ScanEventOut,
    ScanIn,
    ScanOut,
    ScanStats,
    TierScanStat,
)
from app.services import scanning as svc
from app.services.events import VOLUNTEER_GRACE, load_event, society_tz

router = APIRouter(prefix="/societies/{society_id}", tags=["scan"])


@router.get("/scan/events", response_model=list[ScanEventOut])
async def scannable_events(
    ctx: SocietyContext = Depends(require_role(Role.VOLUNTEER)), session: AsyncSession = Depends(get_session)
):
    """Events the caller may scan right now: admins → all live society events; volunteers → active assignments."""
    now = datetime.now(UTC)
    q = (
        select(Event).where(Event.society_id == ctx.sid, Event.status.in_([EventStatus.PUBLISHED.value, EventStatus.CLOSED.value]),
                            Event.ends_at + VOLUNTEER_GRACE > now, Event.starts_at < now + timedelta(days=1))
        .order_by(Event.starts_at)
    )
    if not ctx.is_admin:
        q = q.join(VolunteerAssignment, VolunteerAssignment.event_id == Event.id).where(
            VolunteerAssignment.user_id == ctx.user.id, VolunteerAssignment.expires_at > now)
    events = (await session.scalars(q)).all()
    tz, out = society_tz(ctx.society), []
    for ev in events:
        days = (await session.scalars(select(EventDay).where(EventDay.event_id == ev.id).order_by(EventDay.date))).all()
        day = svc.current_day(ev, list(days), tz, now)
        out.append(ScanEventOut(event_id=ev.id, title=ev.title, venue=ev.venue, starts_at=ev.starts_at, ends_at=ev.ends_at,
                                day=day.date if day else None, counters=await svc.counters(session, ev.id, day)))
    return out


@router.post("/events/{event_id}/scan", response_model=ScanOut)
async def scan(
    event_id: uuid.UUID, body: ScanIn, ctx: SocietyContext = Depends(require_role(Role.VOLUNTEER)),
    session: AsyncSession = Depends(get_session),
):
    """Always 200 with a green/red `ok` verdict for any scanned code (even forged ones); 403/404 only for the
    scanner themself not being allowed to scan this event."""
    ev = await load_event(session, ctx.sid, event_id)
    await svc.authorize_scanner(session, ctx, ev.id)
    return await svc.scan_pass(session, ctx, ev, list(ev.days), body.qr_token, body.gate, body.client_ref)


@router.get("/events/{event_id}/scan-stats", response_model=ScanStats)
async def scan_stats(
    event_id: uuid.UUID, ctx: SocietyContext = Depends(require_role(Role.VOLUNTEER)),
    session: AsyncSession = Depends(get_session),
):
    ev = await load_event(session, ctx.sid, event_id)
    await svc.authorize_scanner(session, ctx, ev.id)
    days = list(ev.days)
    day = svc.current_day(ev, days, society_tz(ctx.society), datetime.now(UTC))
    stats = [DayStat(**d) for d in await svc.day_stats(session, ev.id, days)]
    today = next((s for s in stats if day and s.day_id == day.id), None)
    sold = await session.scalar(select(func.count()).select_from(Pass).where(Pass.event_id == ev.id, Pass.status == PassStatus.ACTIVE.value))
    rows = (await session.execute(
        select(PassTier.id, PassTier.name, func.count(func.distinct(Pass.id)).filter(Pass.status == PassStatus.ACTIVE.value),
               func.count(PassScan.id).filter(PassScan.event_day_id == (day.id if day else None)))
        .select_from(PassTier).outerjoin(Pass, Pass.tier_id == PassTier.id).outerjoin(PassScan, PassScan.pass_id == Pass.id)
        .where(PassTier.event_id == ev.id).group_by(PassTier.id, PassTier.name, PassTier.sort_order).order_by(PassTier.sort_order)
    )).all()
    return ScanStats(sold=sold, today=today, days=stats,
                     by_tier=[TierScanStat(tier_id=r[0], name=r[1], sold=r[2], scanned_today=r[3]) for r in rows])


@router.get("/events/{event_id}/scans", response_model=Page[RecentScan])
async def recent_scans(
    event_id: uuid.UUID, page: PageParams = Depends(), ctx: SocietyContext = Depends(require_role(Role.VOLUNTEER)),
    session: AsyncSession = Depends(get_session),
):
    ev = await load_event(session, ctx.sid, event_id)
    await svc.authorize_scanner(session, ctx, ev.id)
    base = (select(PassScan, Pass, PassTier, User.name).join(Pass, Pass.id == PassScan.pass_id)
            .join(PassTier, PassTier.id == Pass.tier_id).join(User, User.id == PassScan.scanned_by)
            .where(Pass.event_id == ev.id))
    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    rows = (await session.execute(base.order_by(PassScan.scanned_at.desc()).limit(page.limit).offset(page.offset))).all()
    return Page(items=[RecentScan(id=r.PassScan.id, holder_name=r.Pass.holder_name, tier_name=r.PassTier.name,
                                  scanned_at=r.PassScan.scanned_at, scanned_by=r[3], gate=r.PassScan.gate) for r in rows],
                total=total, limit=page.limit, offset=page.offset)
