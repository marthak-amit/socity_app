import uuid

from pydantic import BaseModel, Field

from app.schemas.common import ORM


class OtpRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=20)


class OtpRequestOut(BaseModel):
    sent: bool = True
    retry_after_seconds: int
    dev_otp: str | None = None  # only when OTP_DEV_ECHO=true and not prod


class OtpVerify(BaseModel):
    phone: str
    code: str = Field(min_length=4, max_length=8)


class RefreshIn(BaseModel):
    refresh_token: str


class UserOut(ORM):
    id: uuid.UUID
    phone: str
    name: str | None
    avatar_url: str | None = None
    locale: str = "en"
    is_super_admin: bool = False


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
    is_new_user: bool = False
