"""Presign + consume flow for client uploads (see storage.py for the layout)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import bad_request, not_found
from app.models import Upload, User
from app.models.enums import UploadPurpose
from app.services.images import ALLOWED_CONTENT_TYPES, ProcessedImage, process_image
from app.services.storage import PresignedPut, get_storage

EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def max_bytes_for(purpose: str) -> int:
    s = get_settings()
    return s.max_screenshot_bytes if purpose == UploadPurpose.SCREENSHOT else s.max_image_bytes


async def create_upload(
    session: AsyncSession, user: User, society_id: uuid.UUID | None, purpose: UploadPurpose,
    content_type: str, size: int,
) -> tuple[Upload, PresignedPut]:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise bad_request("unsupported_content_type", "Only JPEG, PNG or WEBP images are allowed")
    limit = max_bytes_for(purpose)
    if size <= 0 or size > limit:
        raise bad_request("file_too_large", f"File must be at most {limit // (1024 * 1024)} MB", max_bytes=limit)
    upload_id = uuid.uuid4()
    key = f"private/raw/{upload_id}"
    up = Upload(
        id=upload_id, key=key, society_id=society_id, user_id=user.id, purpose=purpose.value,
        content_type=content_type, max_bytes=limit,
    )
    session.add(up)
    presigned = await get_storage().presign_put(key, content_type)
    return up, presigned


async def consume_image_upload(
    session: AsyncSession, upload_id: uuid.UUID, user: User, society_id: uuid.UUID | None,
    purpose: UploadPurpose, *, max_side: int = 2048, thumb_side: int | None = None,
) -> tuple[str, str | None, ProcessedImage]:
    """Validate the uploaded object, strip EXIF, write the final object(s).

    Returns (final_key, thumb_key|None, processed_image). The upload row is claimed atomically so a
    token cannot be used twice or by another user/society/purpose.
    """
    storage = get_storage()
    up = await session.scalar(select(Upload).where(Upload.id == upload_id).with_for_update())
    if (
        up is None or up.user_id != user.id or up.society_id != society_id
        or up.purpose != purpose.value or up.consumed_at is not None
    ):
        raise not_found("upload_not_found", "Upload not found or already used")
    size = await storage.object_size(up.key)
    if size is None:
        raise bad_request("upload_missing", "File was not uploaded")
    if size > up.max_bytes:
        await storage.delete_object(up.key)
        raise bad_request("file_too_large", "File is too large", max_bytes=up.max_bytes)
    raw = await storage.get_object(up.key)
    main, thumb = process_image(raw, max_side=max_side, thumb_side=thumb_side)

    private = purpose == UploadPurpose.SCREENSHOT
    scope = f"societies/{society_id}" if society_id else "users"
    base = f"{'private' if private else 'public'}/{scope}/{purpose.value}/{uuid.uuid4()}"
    key = f"{base}.jpg"
    await storage.put_object(key, main.data, "image/jpeg")
    thumb_key = None
    if thumb:
        thumb_key = f"{base}_thumb.jpg"
        await storage.put_object(thumb_key, thumb.data, "image/jpeg")

    await session.execute(update(Upload).where(Upload.id == up.id).values(consumed_at=datetime.now(UTC)))
    await storage.delete_object(up.key)
    return key, thumb_key, main
