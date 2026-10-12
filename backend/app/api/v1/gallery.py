import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.core.db import get_session
from app.core.deps import SocietyContext, require_role
from app.core.errors import conflict, forbidden, not_found
from app.models import Event, GalleryItem
from app.models.enums import EventStatus, GalleryStatus, Role, UploadPurpose
from app.schemas.common import Msg, Page, PageParams
from app.schemas.gallery import GalleryCreate, GalleryItemOut, UploaderOut
from app.services.audit import audit
from app.services.push import push
from app.services.storage import get_storage
from app.services.uploads import consume_image_upload

router = APIRouter(prefix="/societies/{society_id}/gallery", tags=["gallery"])
MAX_PENDING_PER_USER = 50


def _out(g: GalleryItem, ctx: SocietyContext) -> GalleryItemOut:
    st = get_storage()
    return GalleryItemOut(
        id=g.id, event_id=g.event_id, url=st.public_url(g.url_key), thumb_url=st.public_url(g.thumb_key), width=g.width,
        height=g.height, status=GalleryStatus(g.status), uploaded_by=UploaderOut(id=g.uploader.id, name=g.uploader.name),
        mine=g.uploaded_by == ctx.user.id, created_at=g.created_at,
    )


@router.post("", response_model=list[GalleryItemOut], status_code=201)
async def upload_photos(
    body: GalleryCreate, background: BackgroundTasks, ctx: SocietyContext = Depends(require_role(Role.MEMBER)),
    session: AsyncSession = Depends(get_session),
):
    """Admins' photos are published immediately; members' photos wait in the moderation queue."""
    if body.event_id:
        ev = await session.scalar(select(Event).where(Event.id == body.event_id, Event.society_id == ctx.sid))
        if ev is None or (ev.status == EventStatus.DRAFT and not ctx.is_admin):
            raise not_found("event_not_found", "Event not found")
    if not ctx.is_admin:
        pending = await session.scalar(select(func.count()).select_from(GalleryItem).where(
            GalleryItem.society_id == ctx.sid, GalleryItem.uploaded_by == ctx.user.id, GalleryItem.status == GalleryStatus.PENDING.value))
        if pending + len(body.upload_ids) > MAX_PENDING_PER_USER:
            raise conflict("too_many_pending", "You have too many photos awaiting approval")
    status = GalleryStatus.APPROVED if ctx.is_admin else GalleryStatus.PENDING
    items = []
    for upload_id in body.upload_ids:
        key, thumb_key, img = await consume_image_upload(
            session, upload_id, ctx.user, ctx.sid, UploadPurpose.GALLERY, max_side=2048, thumb_side=480)  # EXIF stripped here
        g = GalleryItem(society_id=ctx.sid, event_id=body.event_id, url_key=key, thumb_key=thumb_key, width=img.width,
                        height=img.height, uploaded_by=ctx.user.id, status=status.value,
                        moderated_by=ctx.user.id if ctx.is_admin else None)
        g.uploader = ctx.user
        session.add(g)
        items.append(g)
    await session.flush()
    if not ctx.is_admin:
        from app.api.v1.societies import _admin_user_ids

        background.add_task(push.send, await _admin_user_ids(session, ctx.sid), "Photos to review",
                            f"{ctx.user.name or 'A member'} uploaded {len(items)} photo(s)",
                            {"type": "gallery_pending", "society_id": str(ctx.sid)})
    return [_out(g, ctx) for g in items]


@router.get("", response_model=Page[GalleryItemOut])
async def list_gallery(
    event_id: uuid.UUID | None = Query(None),
    status: GalleryStatus | None = Query(None, description="admins only; members always see approved"),
    mine: bool = Query(False),
    page: PageParams = Depends(),
    ctx: SocietyContext = Depends(require_role(Role.MEMBER)),
    session: AsyncSession = Depends(get_session),
):
    conds = [GalleryItem.society_id == ctx.sid]
    if mine:
        conds.append(GalleryItem.uploaded_by == ctx.user.id)
        if status:
            conds.append(GalleryItem.status == status.value)
    elif ctx.is_admin:
        conds.append(GalleryItem.status == (status or GalleryStatus.APPROVED).value)
    else:
        if status and status != GalleryStatus.APPROVED:
            raise forbidden("insufficient_role", "Only admins can list unapproved photos")
        conds.append(GalleryItem.status == GalleryStatus.APPROVED.value)
    if event_id:
        conds.append(GalleryItem.event_id == event_id)
        ev = await session.scalar(select(Event.ends_at).where(Event.id == event_id, Event.society_id == ctx.sid))
        if ev is None:
            raise not_found("event_not_found", "Event not found")
        if not ctx.is_admin and not mine and ev > datetime.now(UTC):
            return Page(items=[], total=0, limit=page.limit, offset=page.offset)  # event galleries open after the event ends
    total = await session.scalar(select(func.count()).select_from(GalleryItem).where(*conds))
    rows = (await session.scalars(
        select(GalleryItem).where(*conds).order_by(GalleryItem.created_at.desc(), GalleryItem.id)
        .limit(page.limit).offset(page.offset).join(GalleryItem.uploader).options(contains_eager(GalleryItem.uploader))
    )).all()
    return Page(items=[_out(g, ctx) for g in rows], total=total, limit=page.limit, offset=page.offset)


async def _get(session: AsyncSession, ctx: SocietyContext, gid: uuid.UUID) -> GalleryItem:
    g = await session.scalar(select(GalleryItem).where(GalleryItem.id == gid, GalleryItem.society_id == ctx.sid).with_for_update())
    if g is None:
        raise not_found("photo_not_found", "Photo not found")
    await session.refresh(g, ["uploader"])
    return g


async def _moderate(gid, ctx, session, background, status: GalleryStatus):
    g = await _get(session, ctx, gid)
    if g.status != GalleryStatus.PENDING:
        raise conflict("not_pending", f"Photo is already {g.status}")
    g.status, g.moderated_by = status.value, ctx.user.id
    audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action=f"gallery.{status.value}", entity="gallery",
          entity_id=g.id, uploader=g.uploaded_by)
    if status == GalleryStatus.APPROVED:
        background.add_task(push.send, [g.uploaded_by], "Photo approved", "Your photo is now in the gallery",
                            {"type": "gallery_approved", "society_id": str(ctx.sid)})
    return _out(g, ctx)


@router.post("/{gallery_id}/approve", response_model=GalleryItemOut)
async def approve(gallery_id: uuid.UUID, background: BackgroundTasks, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
                  session: AsyncSession = Depends(get_session)):
    return await _moderate(gallery_id, ctx, session, background, GalleryStatus.APPROVED)


@router.post("/{gallery_id}/reject", response_model=GalleryItemOut)
async def reject(gallery_id: uuid.UUID, background: BackgroundTasks, ctx: SocietyContext = Depends(require_role(Role.ADMIN)),
                 session: AsyncSession = Depends(get_session)):
    return await _moderate(gallery_id, ctx, session, background, GalleryStatus.REJECTED)


@router.delete("/{gallery_id}", response_model=Msg)
async def delete_photo(gallery_id: uuid.UUID, ctx: SocietyContext = Depends(require_role(Role.MEMBER)),
                       session: AsyncSession = Depends(get_session)):
    g = await _get(session, ctx, gallery_id)
    if g.uploaded_by != ctx.user.id and not ctx.is_admin:
        raise not_found("photo_not_found", "Photo not found")
    if ctx.is_admin and g.uploaded_by != ctx.user.id:
        audit(session, society_id=ctx.sid, actor_id=ctx.user.id, action="gallery.delete", entity="gallery",
              entity_id=g.id, uploader=g.uploaded_by)
    st = get_storage()
    await st.delete_object(g.url_key)
    await st.delete_object(g.thumb_key)
    await session.delete(g)
    return Msg()
