from fastapi import APIRouter, Depends

from app.core.db import get_session
from app.core.deps import SocietyContext, require_role
from app.core.errors import forbidden
from app.models.enums import Role, UploadPurpose
from app.schemas.users import PresignIn, PresignOut
from app.services.uploads import create_upload

router = APIRouter(prefix="/societies/{society_id}/uploads", tags=["uploads"])

# Which role may request a presigned upload for which purpose.
MIN_ROLE = {
    UploadPurpose.SCREENSHOT: Role.MEMBER,
    UploadPurpose.GALLERY: Role.MEMBER,
    UploadPurpose.BANNER: Role.ADMIN,
    UploadPurpose.LOGO: Role.ADMIN,
}


@router.post("/presign", response_model=PresignOut)
async def presign(
    body: PresignIn,
    ctx: SocietyContext = Depends(require_role(Role.MEMBER)),
    session=Depends(get_session),
):
    """Step 1 of every upload: get a one-shot presigned PUT URL. Step 2: the client PUTs the bytes.
    Step 3: pass `upload_id` to the endpoint that uses the file (order payment, event, gallery...)."""
    needed = MIN_ROLE.get(body.purpose)
    if needed is None:
        raise forbidden("invalid_purpose", "Not a society upload purpose")
    from app.models.enums import ROLE_RANK

    if ROLE_RANK[ctx.role] < ROLE_RANK[needed]:
        raise forbidden("insufficient_role", f"Requires {needed.value} role")
    up, p = await create_upload(session, ctx.user, ctx.sid, body.purpose, body.content_type, body.size)
    return PresignOut(upload_id=up.id, upload_url=p.url, method=p.method, headers=p.headers, max_bytes=up.max_bytes)
