from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.societies import _membership_out
from app.core.db import get_session
from app.core.deps import current_user
from app.models import Membership, PushToken, Society, User
from app.models.enums import MembershipStatus, UploadPurpose
from app.schemas.common import Msg
from app.schemas.users import MeOut, MeUpdate, PresignIn, PresignOut, PushTokenIn
from app.services.serializers import user_out
from app.services.uploads import consume_image_upload, create_upload

router = APIRouter(prefix="/me", tags=["me"])


async def build_me(session: AsyncSession, user: User) -> MeOut:
    rows = (
        await session.execute(
            select(Membership, Society)
            .join(Society, Society.id == Membership.society_id)
            .where(
                Membership.user_id == user.id,
                Membership.status != MembershipStatus.REMOVED.value,
                Society.status != "deleted",
            )
            .order_by(Membership.created_at)
        )
    ).all()
    return MeOut(user=user_out(user), memberships=[_membership_out(m, s) for m, s in rows])


@router.get("", response_model=MeOut)
async def me(user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    return await build_me(session, user)


@router.patch("", response_model=MeOut)
async def update_me(body: MeUpdate, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if body.name is not None:
        user.name = body.name.strip()
    if body.locale is not None:
        user.locale = body.locale
    if body.avatar_upload_id:
        user.avatar_key, _, _ = await consume_image_upload(
            session, body.avatar_upload_id, user, None, UploadPurpose.AVATAR, max_side=512
        )
    await session.flush()
    return await build_me(session, user)


@router.post("/push-tokens", response_model=Msg)
async def register_push_token(
    body: PushTokenIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    # A device token belongs to whoever signed in last on that device.
    stmt = insert(PushToken).values(user_id=user.id, token=body.token, platform=body.platform)
    await session.execute(stmt.on_conflict_do_update(index_elements=[PushToken.token], set_={"user_id": user.id}))
    return Msg()


@router.delete("/push-tokens", response_model=Msg)
async def unregister_push_token(
    body: PushTokenIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    await session.execute(delete(PushToken).where(PushToken.token == body.token, PushToken.user_id == user.id))
    return Msg()


@router.post("/avatar-upload", response_model=PresignOut)
async def presign_avatar(
    body: PresignIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
):
    up, p = await create_upload(session, user, None, UploadPurpose.AVATAR, body.content_type, body.size)
    return PresignOut(upload_id=up.id, upload_url=p.url, method=p.method, headers=p.headers, max_bytes=up.max_bytes)
