import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import Role
from app.schemas.common import ORM

UPI_RE = re.compile(r"^[A-Za-z0-9.\-_]{1,64}@[A-Za-z][A-Za-z0-9]{1,31}$")


def _upi(v: str | None) -> str | None:
    if v is None or v == "":
        return None
    v = v.strip()
    if not UPI_RE.match(v):
        raise ValueError("Invalid UPI ID (expected name@bank)")
    return v


class SocietyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    city: str = Field(min_length=2, max_length=80)
    address: str | None = Field(None, max_length=500)
    upi_id: str | None = None
    upi_name: str | None = Field(None, max_length=100)
    wing: str | None = Field(None, max_length=20)
    flat_no: str | None = Field(None, max_length=20)

    _v_upi = field_validator("upi_id")(_upi)


class SocietyUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    city: str | None = Field(None, min_length=2, max_length=80)
    address: str | None = Field(None, max_length=500)
    upi_id: str | None = None
    upi_name: str | None = Field(None, max_length=100)
    logo_upload_id: uuid.UUID | None = None

    _v_upi = field_validator("upi_id")(_upi)


class SocietyOut(BaseModel):
    id: uuid.UUID
    name: str
    city: str
    address: str | None
    upi_id: str | None
    upi_name: str | None
    logo_url: str | None
    status: str
    timezone: str
    created_at: datetime
    my_role: Role
    invite_code: str | None = None  # admins only
    warnings: list[str] = []  # owner/admin only e.g. "min_two_admins", "upi_not_configured"


class SocietyBrief(BaseModel):
    id: uuid.UUID
    name: str
    city: str
    logo_url: str | None
    status: str


class MembershipOut(BaseModel):
    id: uuid.UUID
    society: SocietyBrief
    role: Role
    status: str
    flat_no: str | None
    wing: str | None


class LookupIn(BaseModel):
    invite_code: str = Field(min_length=4, max_length=12)


class JoinIn(BaseModel):
    invite_code: str = Field(min_length=4, max_length=12)
    wing: str | None = Field(None, max_length=20)
    flat_no: str | None = Field(None, max_length=20)


class InviteOut(BaseModel):
    code: str
    deep_link: str
    web_link: str
    share_text: str


class DeleteSocietyIn(BaseModel):
    confirm_name: str


class MemberOut(ORM):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str | None
    phone: str
    role: Role
    status: str
    flat_no: str | None
    wing: str | None
    created_at: datetime


class MemberUpdate(BaseModel):
    role: Role | None = None
    flat_no: str | None = Field(None, max_length=20)
    wing: str | None = Field(None, max_length=20)


class MemberChangeOut(BaseModel):
    member: MemberOut
    warnings: list[str] = []


class ImportIn(BaseModel):
    csv_text: str = Field(max_length=500_000)


class ImportOut(BaseModel):
    created: int
    updated: int
    activated: int
    errors: list[dict]
