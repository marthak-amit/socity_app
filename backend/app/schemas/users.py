import uuid

from pydantic import BaseModel, Field

from app.models.enums import UploadPurpose
from app.schemas.auth import UserOut
from app.schemas.societies import MembershipOut


class MeOut(BaseModel):
    user: UserOut
    memberships: list[MembershipOut]


class MeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    locale: str | None = Field(None, pattern="^(en|gu|hi)$")
    avatar_upload_id: uuid.UUID | None = None


class PushTokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    platform: str | None = Field(None, max_length=20)


class PresignIn(BaseModel):
    purpose: UploadPurpose
    content_type: str
    size: int = Field(gt=0)


class PresignOut(BaseModel):
    upload_id: uuid.UUID
    upload_url: str
    method: str
    headers: dict[str, str]
    max_bytes: int
