import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import GalleryStatus


class GalleryCreate(BaseModel):
    event_id: uuid.UUID | None = None
    upload_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)


class UploaderOut(BaseModel):
    id: uuid.UUID
    name: str | None


class GalleryItemOut(BaseModel):
    id: uuid.UUID
    event_id: uuid.UUID | None
    url: str
    thumb_url: str
    width: int | None
    height: int | None
    status: GalleryStatus
    uploaded_by: UploaderOut
    mine: bool
    created_at: datetime
