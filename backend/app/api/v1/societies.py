import csv
import io
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import SocietyContext, current_user, require_role
from app.core.errors import bad_request, conflict, forbidden, not_found
from app.core.phone import try_normalize_phone
from app.core.rate_limit import limiter
from app.models import Membership, PreapprovedMember, Society, User
from app.models.enums import MembershipStatus, Role, SocietyStatus, UploadPurpose
from app.schemas.common import Msg, Page, PageParams
from app.schemas.societies import (
    DeleteSocietyIn,
    ImportIn,
    ImportOut,
    InviteOut,
    JoinIn,
    LookupIn,
    MemberChangeOut,
    MemberOut,
    MembershipOut,
    MemberUpdate,
    SocietyBrief,
    SocietyCreate,
    SocietyOut,
    SocietyUpdate,
)
from app.services.audit import audit
from app.services.push import push
from app.services.societies import (
    ADMIN_ROLES,
    brief,
    invite_links,
    society_out,
    society_warnings,
    unique_invite_code,
)
from app.services.uploads import consume_image_upload

router = APIRouter(prefix="/societies", tags=["societies"])


def _membership_out(m: Membership, s: Society) -> MembershipOut:
    return MembershipOut(id=m.id, society=brief(s), role=Role(m.role), status=m.status, flat_no=m.flat_no, wing=m.wing)


def _member_out(m: Membership, u: User) -> MemberOut:
    return MemberOut(
        id=m.id, user_id=u.id, name=u.name, phone=u.phone, role=Role(m.role), status=m.status,
        flat_no=m.flat_no, wing=m.wing, created_at=m.created_at,
    )


async def _admin_user_ids(session: AsyncSession, society_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        (
            await session.scalars(
                select(Membership.user_id).where(
                    Membership.society_id == society_id, Membership.status == MembershipStatus.ACTIVE,
                    Membership.role.in_(ADMIN_ROLES),
                )
            )
        ).all()
    )


# ------------------------------------------------------------------ create / join (not society-scoped yet)
@router.post("", response_model=SocietyOut, status_code=201)
async def create_society(
    body: SocietyCreate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    society = Society(
        name=body.name.strip(), city=body.city.strip(), address=body.address, upi_id=body.upi_id,
        upi_name=body.upi_name, invite_code=await unique_invite_code(session), created_by=user.id,
    )
    session.add(society)
    await session.flush()
    session.add(
        Membership(
            user_id=user.id, society_id=society.id, role=Role.OWNER.value, status=MembershipStatus.ACTIVE.value,
            flat_no=body.flat_no, wing=body.wing, approved_by=user.id,
        )
    )
    audit(session, society_id=society.id, actor_id=user.id, action="society.create", entity="society",
          entity_id=society.id, name=society.name)
    return await society_out(session, society, Role.OWNER)


@router.post("/lookup", response_model=SocietyBrief)
async def lookup_society(
    body: LookupIn, request: Request, user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    limiter.check(f"lookup:{user.id}", 20, 600)  # stop invite-code enumeration
    s = await session.scalar(select(Society).where(Society.invite_code == body.invite_code.strip().upper()))
    if s is None or s.status == SocietyStatus.DELETED:
        raise not_found("invalid_invite_code", "No society found for this code")
    return brief(s)


@router.post("/join", response_model=MembershipOut, status_code=201)
async def join_society(
    body: JoinIn, background: BackgroundTasks, user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    limiter.check(f"join:{user.id}", 20, 600)
    society = await session.scalar(select(Society).where(Society.invite_code == body.invite_code.strip().upper()))
    if society is None or society.status == SocietyStatus.DELETED:
        raise not_found("invalid_invite_code", "No society found for this code")
    if society.status == SocietyStatus.SUSPENDED:
        raise forbidden("society_suspended", "This society has been suspended by the platform")

    m = await session.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.society_id == society.id).with_for_update()
    )
    if m is not None and m.status == MembershipStatus.ACTIVE:
        raise conflict("already_member", "You are already a member of this society")

    pre = await session.scalar(
        select(PreapprovedMember).where(PreapprovedMember.society_id == society.id, PreapprovedMember.phone == user.phone)
    )
    wing = body.wing or (pre.wing if pre else None)
    flat = body.flat_no or (pre.flat_no if pre else None)
    if m is None:
        m = Membership(user_id=user.id, society_id=society.id, role=Role.MEMBER.value)
        session.add(m)
    m.wing, m.flat_no = wing, flat
    if pre is not None:
        m.status = MembershipStatus.ACTIVE.value
        m.role = Role.MEMBER.value
        audit(session, society_id=society.id, actor_id=user.id, action="member.auto_approve", entity="membership",
              entity_id=m.id, via="csv_import")
        if not user.name and pre.name:
            user.name = pre.name
    else:
        m.status = MembershipStatus.PENDING.value
        m.created_at = datetime.now(UTC)
        admins = await _admin_user_ids(session, society.id)
        background.add_task(
            push.send, admins, "New join request", f"{user.name or user.phone} wants to join {society.name}",
            {"type": "join_request", "society_id": str(society.id)},
        )
    await session.flush()
    return _membership_out(m, society)


# ------------------------------------------------------------------ society detail
@router.get("/{society_id}", response_model=SocietyOut)
async def get_society(
    ctx: SocietyContext = Depends(require_role(Role.MEMBER, allow_suspended=True)),
    session: AsyncSession = Depends(get_session),
):
    return await society_out(session, ctx.society, ctx.role)


@router.patch("/{society_id}", response_model=SocietyOut)
async def update_society(
    body: SocietyUpdate, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    s = ctx.society
    changes: dict = {}
    for field in ("name", "city", "address", "upi_name"):
        v = getattr(body, field)
        if v is not None and v != getattr(s, field):
            changes[field] = v
            setattr(s, field, v)
    if body.upi_id is not None and body.upi_id != s.upi_id:
        changes["upi_id"] = {"from": s.upi_id, "to": body.upi_id}  # payment destination → always audited
        s.upi_id = body.upi_id
    if body.logo_upload_id:
        s.logo_key, _, _ = await consume_image_upload(
            session, body.logo_upload_id, ctx.user, s.id, UploadPurpose.LOGO, max_side=512
        )
        changes["logo"] = True
    if changes:
        audit(session, society_id=s.id, actor_id=ctx.user.id, action="society.update", entity="society",
              entity_id=s.id, changes=changes)
    return await society_out(session, s, ctx.role)


@router.delete("/{society_id}", response_model=Msg)
async def delete_society(
    body: DeleteSocietyIn, ctx: SocietyContext = Depends(require_role(Role.OWNER, allow_suspended=True)),
    session: AsyncSession = Depends(get_session),
):
    if body.confirm_name.strip() != ctx.society.name:
        raise bad_request("confirmation_mismatch", "Type the society name exactly to confirm deletion")
    ctx.society.status = SocietyStatus.DELETED.value
    ctx.society.deleted_at = datetime.now(UTC)
    audit(session, society_id=ctx.society.id, actor_id=ctx.user.id, action="society.delete", entity="society",
          entity_id=ctx.society.id, name=ctx.society.name)
    return Msg(message="Society deleted")


@router.get("/{society_id}/invite", response_model=InviteOut)
async def get_invite(ctx: SocietyContext = Depends(require_role(Role.ADMIN))):
    code = ctx.society.invite_code
    deep, web = invite_links(code)
    return InviteOut(
        code=code, deep_link=deep, web_link=web,
        share_text=f"Join {ctx.society.name} on SocietyPass! Use invite code {code} or open {web}",
    )


@router.post("/{society_id}/invite/rotate", response_model=InviteOut)
async def rotate_invite(
    ctx: SocietyContext = Depends(require_role(Role.ADMIN)), session: AsyncSession = Depends(get_session)
):
    ctx.society.invite_code = await unique_invite_code(session)
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="society.invite_rotate", entity="society",
          entity_id=ctx.sid)
    return await get_invite(ctx)


# ------------------------------------------------------------------ members
@router.get("/{society_id}/members", response_model=Page[MemberOut])
async def list_members(
    status: MembershipStatus | None = Query(None),
    role: Role | None = Query(None),
    q: str | None = Query(None, max_length=50),
    page: PageParams = Depends(),
    ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    conds = [Membership.society_id == ctx.sid]
    conds.append(Membership.status == status.value if status else Membership.status != MembershipStatus.REMOVED.value)
    if role:
        conds.append(Membership.role == role.value)
    if q:
        like = f"%{q.strip()}%"
        conds.append(or_(User.name.ilike(like), User.phone.ilike(like), Membership.flat_no.ilike(like),
                         Membership.wing.ilike(like)))
    base = select(Membership, User).join(User, User.id == Membership.user_id).where(*conds)
    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    rows = (await session.execute(
        base.order_by(Membership.created_at.desc()).limit(page.limit).offset(page.offset)
    )).all()
    return Page(items=[_member_out(m, u) for m, u in rows], total=total, limit=page.limit, offset=page.offset)


async def _get_member(session: AsyncSession, ctx: SocietyContext, member_id: uuid.UUID):
    row = (await session.execute(
        select(Membership, User).join(User, User.id == Membership.user_id)
        .where(Membership.id == member_id, Membership.society_id == ctx.sid).with_for_update(of=Membership)
    )).first()
    if row is None:
        raise not_found("member_not_found", "Member not found")
    return row.Membership, row.User


@router.post("/{society_id}/members/{member_id}/approve", response_model=MemberChangeOut)
async def approve_member(
    member_id: uuid.UUID, background: BackgroundTasks,
    ctx: SocietyContext = Depends(require_role(Role.ADMIN)), session: AsyncSession = Depends(get_session),
):
    m, u = await _get_member(session, ctx, member_id)
    if m.status != MembershipStatus.PENDING:
        raise conflict("not_pending", "This request is not pending")
    m.status, m.approved_by = MembershipStatus.ACTIVE.value, ctx.user.id
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="member.approve", entity="membership",
          entity_id=m.id, user_id=u.id)
    background.add_task(
        push.send, [u.id], "Welcome!", f"Your request to join {ctx.society.name} was approved",
        {"type": "join_approved", "society_id": str(ctx.sid)},
    )
    return MemberChangeOut(member=_member_out(m, u))


@router.post("/{society_id}/members/{member_id}/reject", response_model=MemberChangeOut)
async def reject_member(
    member_id: uuid.UUID, background: BackgroundTasks,
    ctx: SocietyContext = Depends(require_role(Role.ADMIN)), session: AsyncSession = Depends(get_session),
):
    m, u = await _get_member(session, ctx, member_id)
    if m.status != MembershipStatus.PENDING:
        raise conflict("not_pending", "This request is not pending")
    m.status = MembershipStatus.REMOVED.value
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="member.reject", entity="membership",
          entity_id=m.id, user_id=u.id)
    background.add_task(
        push.send, [u.id], "Request declined", f"Your request to join {ctx.society.name} was declined",
        {"type": "join_rejected", "society_id": str(ctx.sid)},
    )
    return MemberChangeOut(member=_member_out(m, u))


def _can_manage(actor: Role, target: Role) -> bool:
    """Owner manages everyone but owners; admins manage only members/volunteers."""
    if target == Role.OWNER:
        return False
    return actor == Role.OWNER or (actor == Role.ADMIN and target in (Role.MEMBER, Role.VOLUNTEER))


@router.patch("/{society_id}/members/{member_id}", response_model=MemberChangeOut)
async def update_member(
    member_id: uuid.UUID, body: MemberUpdate,
    ctx: SocietyContext = Depends(require_role(Role.ADMIN)), session: AsyncSession = Depends(get_session),
):
    m, u = await _get_member(session, ctx, member_id)
    if m.status == MembershipStatus.REMOVED:
        raise not_found("member_not_found", "Member not found")
    if body.role is not None and body.role.value != m.role:
        if m.user_id == ctx.user.id:
            raise forbidden("cannot_change_own_role", "You cannot change your own role")
        if body.role == Role.OWNER:
            raise forbidden("owner_role_reserved", "The owner role cannot be assigned")
        if not _can_manage(ctx.role, Role(m.role)) or not _can_manage(ctx.role, body.role):
            raise forbidden("insufficient_role", "You cannot make this role change")
        audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="member.role_change", entity="membership",
              entity_id=m.id, user_id=u.id, from_role=m.role, to_role=body.role.value)
        m.role = body.role.value
    if body.flat_no is not None:
        m.flat_no = body.flat_no
    if body.wing is not None:
        m.wing = body.wing
    await session.flush()
    return MemberChangeOut(member=_member_out(m, u), warnings=await society_warnings(session, ctx.society))


@router.delete("/{society_id}/members/{member_id}", response_model=MemberChangeOut)
async def remove_member(
    member_id: uuid.UUID, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_session),
):
    m, u = await _get_member(session, ctx, member_id)
    if m.user_id == ctx.user.id:
        raise forbidden("cannot_remove_self", "Use 'leave society' instead")
    if not _can_manage(ctx.role, Role(m.role)):
        raise forbidden("insufficient_role", "You cannot remove this member")
    m.status = MembershipStatus.REMOVED.value
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="member.remove", entity="membership",
          entity_id=m.id, user_id=u.id, role=m.role)
    await session.flush()
    return MemberChangeOut(member=_member_out(m, u), warnings=await society_warnings(session, ctx.society))


@router.post("/{society_id}/leave", response_model=Msg)
async def leave_society(ctx: SocietyContext = Depends(require_role(Role.MEMBER, allow_suspended=True)),
                        session: AsyncSession = Depends(get_session)):
    if ctx.role == Role.OWNER:
        raise forbidden("owner_cannot_leave", "Owners cannot leave; delete the society instead")
    ctx.membership.status = MembershipStatus.REMOVED.value
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="member.leave", entity="membership",
          entity_id=ctx.membership.id)
    return Msg()


@router.post("/{society_id}/members/import", response_model=ImportOut)
async def import_members(
    body: ImportIn, background: BackgroundTasks,
    ctx: SocietyContext = Depends(require_role(Role.ADMIN)), session: AsyncSession = Depends(get_session),
):
    """CSV with header `phone,name,wing,flat_no`. Listed phones are auto-approved when they join; people
    already waiting in the pending queue are approved immediately."""
    reader = csv.DictReader(io.StringIO(body.csv_text.strip()))
    if not reader.fieldnames or "phone" not in [f.strip().lower() for f in reader.fieldnames]:
        raise bad_request("invalid_csv", "CSV must have a header row with at least a 'phone' column")
    created = updated = activated = 0
    errors: list[dict] = []
    seen: dict[str, dict] = {}
    for i, raw in enumerate(reader, start=2):
        if i > 2001:
            errors.append({"row": i, "error": "row limit (2000) exceeded"})
            break
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        phone = try_normalize_phone(row.get("phone", ""))
        if not phone:
            errors.append({"row": i, "error": "invalid phone"})
            continue
        seen[phone] = row
    if seen:
        existing = {
            p.phone: p for p in (await session.scalars(
                select(PreapprovedMember).where(PreapprovedMember.society_id == ctx.sid, PreapprovedMember.phone.in_(seen))
            )).all()
        }
        for phone, row in seen.items():
            p = existing.get(phone)
            if p is None:
                session.add(PreapprovedMember(society_id=ctx.sid, phone=phone, name=row.get("name") or None,
                                              wing=row.get("wing") or None, flat_no=row.get("flat_no") or row.get("flat") or None))
                created += 1
            else:
                p.name, p.wing = row.get("name") or p.name, row.get("wing") or p.wing
                p.flat_no = row.get("flat_no") or row.get("flat") or p.flat_no
                updated += 1
        pending = (await session.execute(
            select(Membership, User).join(User, User.id == Membership.user_id).where(
                Membership.society_id == ctx.sid, Membership.status == MembershipStatus.PENDING.value, User.phone.in_(seen))
        )).all()
        for m, u in pending:
            m.status, m.approved_by = MembershipStatus.ACTIVE.value, ctx.user.id
            row = seen[u.phone]
            m.wing = m.wing or row.get("wing") or None
            m.flat_no = m.flat_no or row.get("flat_no") or row.get("flat") or None
            activated += 1
            background.add_task(push.send, [u.id], "Welcome!", f"You have been added to {ctx.society.name}",
                                {"type": "join_approved", "society_id": str(ctx.sid)})
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="member.import", entity="society",
          entity_id=ctx.sid, created=created, updated=updated, activated=activated)
    return ImportOut(created=created, updated=updated, activated=activated, errors=errors)
