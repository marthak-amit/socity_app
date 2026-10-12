import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import SocietyContext, current_user, require_role
from app.core.errors import conflict, not_found
from app.models import Event, EventDay, Pass, PassScan, PassTier, PassTierDay, Society, User
from app.models.enums import PassStatus, Role, ValidDays
from app.schemas.common import Msg, Page, PageParams
from app.schemas.orders import PassEventOut, PassOut
from app.services.audit import audit
from app.services.storage import get_storage

router = APIRouter(tags=["passes"])


async def passes_out(session: AsyncSession, rows) -> list[PassOut]:
    """rows: [(Pass, Event, Society, PassTier)] → PassOut with batched valid-day + scan lookups."""
    if not rows:
        return []
    tier_ids = {r.PassTier.id for r in rows}
    pass_ids = [r.Pass.id for r in rows]
    valid: dict[uuid.UUID, list] = defaultdict(list)
    for tid, d in (await session.execute(
        select(PassTierDay.tier_id, EventDay.date).join(EventDay, EventDay.id == PassTierDay.event_day_id)
        .where(PassTierDay.tier_id.in_(tier_ids)).order_by(EventDay.date)
    )).all():
        valid[tid].append(d)
    scanned: dict[uuid.UUID, list] = defaultdict(list)
    for pid, d in (await session.execute(
        select(PassScan.pass_id, EventDay.date).join(EventDay, EventDay.id == PassScan.event_day_id)
        .where(PassScan.pass_id.in_(pass_ids)).order_by(EventDay.date)
    )).all():
        scanned[pid].append(d)
    storage = get_storage()
    return [
        PassOut(
            id=r.Pass.id, order_id=r.Pass.order_id, tier_id=r.PassTier.id, tier_name=r.PassTier.name,
            holder_name=r.Pass.holder_name, holder_type=r.Pass.holder_type, qr_token=r.Pass.qr_token,
            status=PassStatus(r.Pass.status), valid_days=ValidDays(r.PassTier.valid_days),
            valid_dates=valid.get(r.PassTier.id, []), scanned_dates=scanned.get(r.Pass.id, []),
            created_at=r.Pass.created_at,
            event=PassEventOut(
                id=r.Event.id, society_id=r.Society.id, society_name=r.Society.name, title=r.Event.title,
                venue=r.Event.venue, starts_at=r.Event.starts_at, ends_at=r.Event.ends_at,
                banner_url=storage.url_for(r.Event.banner_key),
            ),
        )
        for r in rows
    ]


def _base(user_id: uuid.UUID):
    return (
        select(Pass, Event, Society, PassTier)
        .join(Event, Event.id == Pass.event_id).join(Society, Society.id == Pass.society_id)
        .join(PassTier, PassTier.id == Pass.tier_id).where(Pass.user_id == user_id, Society.status != "deleted")
    )


@router.get("/me/passes", response_model=Page[PassOut], summary="My passes across all my societies")
async def my_passes_everywhere(
    event_id: uuid.UUID | None = Query(None), page: PageParams = Depends(),
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
):
    """Only returns the caller's own passes (user_id filter), for societies they still belong to."""
    from app.models import Membership
    from app.models.enums import MembershipStatus

    q = _base(user.id).where(
        Pass.society_id.in_(select(Membership.society_id).where(
            Membership.user_id == user.id, Membership.status == MembershipStatus.ACTIVE.value))
    )
    if event_id:
        q = q.where(Pass.event_id == event_id)
    total = await session.scalar(select(func.count()).select_from(q.subquery()))
    rows = (await session.execute(q.order_by(Event.starts_at.desc(), Pass.created_at).limit(page.limit).offset(page.offset))).all()
    return Page(items=await passes_out(session, rows), total=total, limit=page.limit, offset=page.offset)


@router.get("/societies/{society_id}/passes/mine", response_model=Page[PassOut])
async def my_passes(
    event_id: uuid.UUID | None = Query(None), page: PageParams = Depends(),
    ctx: SocietyContext = Depends(require_role(Role.MEMBER)), session: AsyncSession = Depends(get_session),
):
    q = _base(ctx.user.id).where(Pass.society_id == ctx.sid)
    if event_id:
        q = q.where(Pass.event_id == event_id)
    total = await session.scalar(select(func.count()).select_from(q.subquery()))
    rows = (await session.execute(q.order_by(Event.starts_at.desc(), Pass.created_at).limit(page.limit).offset(page.offset))).all()
    return Page(items=await passes_out(session, rows), total=total, limit=page.limit, offset=page.offset)


@router.post("/societies/{society_id}/passes/{pass_id}/revoke", response_model=Msg)
async def revoke_pass(
    pass_id: uuid.UUID, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    p = await session.scalar(select(Pass).where(Pass.id == pass_id, Pass.society_id == ctx.sid).with_for_update())
    if p is None:
        raise not_found("pass_not_found", "Pass not found")
    if p.status == PassStatus.REVOKED:
        raise conflict("already_revoked", "Pass already revoked")
    p.status = PassStatus.REVOKED.value
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="pass.revoke", entity="pass", entity_id=p.id,
          holder=p.holder_name, order_id=p.order_id)
    return Msg()
