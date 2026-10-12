"""Platform (super-admin) API. Deliberately exposes NO payment screenshots — those are visible only to the admins
of the owning society."""

import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import current_super_admin
from app.core.errors import conflict, not_found
from app.models import AuditLog, Event, Membership, Order, Pass, PassScan, Society, User
from app.models.enums import MembershipStatus, OrderStatus, SocietyStatus
from app.schemas.common import Msg, Page, PageParams
from app.services.audit import audit
from app.services.push import push
from app.services.societies import ADMIN_ROLES
from app.services.storage import get_storage

router = APIRouter(prefix="/admin", tags=["super-admin"], dependencies=[Depends(current_super_admin)])


class PlatformStats(BaseModel):
    societies: dict[str, int]
    users: int
    active_members: int
    events: dict[str, int]
    orders: dict[str, int]
    collected_amount: int
    flagged_pending_orders: int
    passes: int
    scans: int


class AdminSociety(BaseModel):
    id: uuid.UUID
    name: str
    city: str
    status: str
    logo_url: str | None
    created_at: datetime
    members: int
    admins: int
    events: int
    collected_amount: int
    owner_name: str | None = None
    owner_phone: str | None = None


class SuspendIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


class FlaggedOrder(BaseModel):
    id: uuid.UUID
    ref_code: str
    society_id: uuid.UUID
    society_name: str
    event_title: str
    status: str
    total_amount: int
    paid_amount: int | None
    utr: str | None
    flags: list[str]
    buyer_name: str | None
    buyer_phone: str
    created_at: datetime


class AuditRow(BaseModel):
    id: int
    created_at: datetime
    society_id: uuid.UUID | None
    society_name: str | None
    actor_id: uuid.UUID | None
    actor_name: str | None
    actor_phone: str | None
    action: str
    entity: str
    entity_id: str | None
    meta: dict


async def _count_map(session: AsyncSession, col, table_filter=None) -> dict[str, int]:
    q = select(col, func.count()).group_by(col)
    return {k: n for k, n in (await session.execute(q)).all()}


@router.get("/stats", response_model=PlatformStats)
async def stats(session: AsyncSession = Depends(get_session)):
    return PlatformStats(
        societies=await _count_map(session, Society.status),
        users=await session.scalar(select(func.count()).select_from(User)),
        active_members=await session.scalar(select(func.count()).select_from(Membership).where(Membership.status == MembershipStatus.ACTIVE.value)),
        events=await _count_map(session, Event.status),
        orders=await _count_map(session, Order.status),
        collected_amount=int(await session.scalar(select(func.coalesce(func.sum(Order.total_amount), 0)).where(Order.status == OrderStatus.APPROVED.value))),
        flagged_pending_orders=await session.scalar(select(func.count()).select_from(Order).where(
            Order.status == OrderStatus.PENDING.value, func.jsonb_array_length(Order.flags) > 0)),
        passes=await session.scalar(select(func.count()).select_from(Pass)),
        scans=await session.scalar(select(func.count()).select_from(PassScan)),
    )


async def _society_rows(session: AsyncSession, societies: list[Society]) -> list[AdminSociety]:
    ids = [s.id for s in societies]
    if not ids:
        return []
    members = dict((await session.execute(select(Membership.society_id, func.count()).where(
        Membership.society_id.in_(ids), Membership.status == MembershipStatus.ACTIVE.value).group_by(Membership.society_id))).all())
    admins = dict((await session.execute(select(Membership.society_id, func.count()).where(
        Membership.society_id.in_(ids), Membership.status == MembershipStatus.ACTIVE.value,
        Membership.role.in_(ADMIN_ROLES)).group_by(Membership.society_id))).all())
    events = dict((await session.execute(select(Event.society_id, func.count()).where(Event.society_id.in_(ids)).group_by(Event.society_id))).all())
    collected = dict((await session.execute(select(Order.society_id, func.coalesce(func.sum(Order.total_amount), 0)).where(
        Order.society_id.in_(ids), Order.status == OrderStatus.APPROVED.value).group_by(Order.society_id))).all())
    owners = {m.society_id: u for m, u in (await session.execute(
        select(Membership, User).join(User, User.id == Membership.user_id).where(
            Membership.society_id.in_(ids), Membership.role == "owner", Membership.status == MembershipStatus.ACTIVE.value))).all()}
    st = get_storage()
    return [AdminSociety(
        id=s.id, name=s.name, city=s.city, status=s.status, logo_url=st.url_for(s.logo_key), created_at=s.created_at,
        members=members.get(s.id, 0), admins=admins.get(s.id, 0), events=events.get(s.id, 0), collected_amount=int(collected.get(s.id, 0)),
        owner_name=owners[s.id].name if s.id in owners else None, owner_phone=owners[s.id].phone if s.id in owners else None,
    ) for s in societies]


@router.get("/societies", response_model=Page[AdminSociety])
async def list_societies(
    q: str | None = Query(None, max_length=60), status: SocietyStatus | None = Query(None),
    page: PageParams = Depends(), session: AsyncSession = Depends(get_session),
):
    conds = []
    if status:
        conds.append(Society.status == status.value)
    if q:
        conds.append(Society.name.ilike(f"%{q.strip()}%") | Society.city.ilike(f"%{q.strip()}%"))
    total = await session.scalar(select(func.count()).select_from(Society).where(*conds))
    rows = (await session.scalars(select(Society).where(*conds).order_by(Society.created_at.desc()).limit(page.limit).offset(page.offset))).all()
    return Page(items=await _society_rows(session, list(rows)), total=total, limit=page.limit, offset=page.offset)


@router.get("/societies/{society_id}", response_model=AdminSociety)
async def get_society(society_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    s = await session.get(Society, society_id)
    if s is None:
        raise not_found("society_not_found", "Society not found")
    return (await _society_rows(session, [s]))[0]


@router.post("/societies/{society_id}/suspend", response_model=AdminSociety)
async def suspend(
    society_id: uuid.UUID, body: SuspendIn, background: BackgroundTasks, actor: User = Depends(current_super_admin),
    session: AsyncSession = Depends(get_session),
):
    s = await session.scalar(select(Society).where(Society.id == society_id).with_for_update())
    if s is None or s.status == SocietyStatus.DELETED:
        raise not_found("society_not_found", "Society not found")
    if s.status == SocietyStatus.SUSPENDED:
        raise conflict("already_suspended", "Society is already suspended")
    s.status = SocietyStatus.SUSPENDED.value
    audit(session, society_id=s.id, actor_id=actor.id, action="society.suspend", entity="society", entity_id=s.id, reason=body.reason)
    admins = list((await session.scalars(select(Membership.user_id).where(
        Membership.society_id == s.id, Membership.role.in_(ADMIN_ROLES), Membership.status == MembershipStatus.ACTIVE.value))).all())
    background.add_task(push.send, admins, "Society suspended", f"{s.name} was suspended by the platform: {body.reason}",
                        {"type": "society_suspended", "society_id": str(s.id)})
    await session.flush()
    return (await _society_rows(session, [s]))[0]


@router.post("/societies/{society_id}/unsuspend", response_model=AdminSociety)
async def unsuspend(society_id: uuid.UUID, actor: User = Depends(current_super_admin), session: AsyncSession = Depends(get_session)):
    s = await session.scalar(select(Society).where(Society.id == society_id).with_for_update())
    if s is None or s.status == SocietyStatus.DELETED:
        raise not_found("society_not_found", "Society not found")
    if s.status != SocietyStatus.SUSPENDED:
        raise conflict("not_suspended", "Society is not suspended")
    s.status = SocietyStatus.ACTIVE.value
    audit(session, society_id=s.id, actor_id=actor.id, action="society.unsuspend", entity="society", entity_id=s.id)
    await session.flush()
    return (await _society_rows(session, [s]))[0]


@router.get("/orders/flagged", response_model=Page[FlaggedOrder])
async def flagged_orders(
    status: OrderStatus | None = Query(OrderStatus.PENDING), society_id: uuid.UUID | None = Query(None),
    page: PageParams = Depends(), session: AsyncSession = Depends(get_session),
):
    conds = [func.jsonb_array_length(Order.flags) > 0]
    if status:
        conds.append(Order.status == status.value)
    if society_id:
        conds.append(Order.society_id == society_id)
    total = await session.scalar(select(func.count()).select_from(Order).where(*conds))
    rows = (await session.execute(
        select(Order, Society.name, Event.title, User).join(Society, Society.id == Order.society_id)
        .join(Event, Event.id == Order.event_id).join(User, User.id == Order.user_id).where(*conds)
        .order_by(Order.created_at.desc()).limit(page.limit).offset(page.offset))).all()
    return Page(items=[FlaggedOrder(
        id=o.id, ref_code=o.ref_code, society_id=o.society_id, society_name=sn, event_title=et, status=o.status,
        total_amount=o.total_amount, paid_amount=o.paid_amount, utr=o.utr, flags=list(o.flags), buyer_name=u.name,
        buyer_phone=u.phone, created_at=o.created_at) for o, sn, et, u in rows], total=total, limit=page.limit, offset=page.offset)


@router.get("/audit-logs", response_model=Page[AuditRow])
async def audit_logs(
    society_id: uuid.UUID | None = Query(None), action: str | None = Query(None, max_length=60),
    actor_id: uuid.UUID | None = Query(None), page: PageParams = Depends(), session: AsyncSession = Depends(get_session),
):
    conds = []
    if society_id:
        conds.append(AuditLog.society_id == society_id)
    if action:
        conds.append(AuditLog.action.ilike(f"{action}%"))
    if actor_id:
        conds.append(AuditLog.actor_id == actor_id)
    total = await session.scalar(select(func.count()).select_from(AuditLog).where(*conds))
    rows = (await session.execute(
        select(AuditLog, Society.name, User.name, User.phone).outerjoin(Society, Society.id == AuditLog.society_id)
        .outerjoin(User, User.id == AuditLog.actor_id).where(*conds)
        .order_by(AuditLog.id.desc()).limit(page.limit).offset(page.offset))).all()
    return Page(items=[AuditRow(
        id=a.id, created_at=a.created_at, society_id=a.society_id, society_name=sn, actor_id=a.actor_id, actor_name=an,
        actor_phone=ap, action=a.action, entity=a.entity, entity_id=a.entity_id, meta=a.meta) for a, sn, an, ap in rows],
        total=total, limit=page.limit, offset=page.offset)


@router.get("/ping", response_model=Msg)
async def ping():
    return Msg(message="pong")
