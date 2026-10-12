import re
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import HolderType, OrderFlag, OrderStatus, PassStatus, ValidDays


class HolderIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: HolderType = HolderType.GUEST


class OrderItemIn(BaseModel):
    tier_id: uuid.UUID
    qty: int = Field(ge=1, le=50)
    holders: list[HolderIn] = []


class OrderCreate(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1, max_length=10)


class PaymentSubmit(BaseModel):
    screenshot_upload_id: uuid.UUID | None = None
    utr: str | None = None
    paid_amount: int | None = Field(None, ge=0, le=10_000_000)

    @field_validator("utr")
    @classmethod
    def _utr(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        v = re.sub(r"\s+", "", v)
        if not re.fullmatch(r"\d{12}", v):
            raise ValueError("UTR must be exactly 12 digits")
        return v


class RejectIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


class BulkApproveIn(BaseModel):
    order_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    include_flagged: bool = False


class BulkApproveOut(BaseModel):
    approved: list[uuid.UUID]
    skipped: list[dict]


class OrderItemOut(BaseModel):
    tier_id: uuid.UUID
    tier_name: str
    qty: int
    unit_price: int
    holders: list[dict]


class PaymentInstructionsOut(BaseModel):
    provider: str
    amount: int
    currency: str
    upi_id: str | None
    payee_name: str | None
    note: str | None
    upi_uri: str | None
    requires_proof: bool


class OrderMemberOut(BaseModel):
    user_id: uuid.UUID
    name: str | None
    phone: str
    wing: str | None
    flat_no: str | None


class OrderOut(BaseModel):
    id: uuid.UUID
    ref_code: str
    event_id: uuid.UUID
    event_title: str
    society_id: uuid.UUID
    status: OrderStatus
    total_amount: int
    paid_amount: int | None
    utr: str | None
    has_screenshot: bool
    screenshot_url: str | None = None  # admins only; short-lived presigned URL
    payment_submitted_at: datetime | None
    flags: list[OrderFlag] = []  # admins only
    reject_reason: str | None
    reviewed_at: datetime | None
    created_at: datetime
    expires_at: datetime | None  # unpaid pending orders release their seats at this time
    items: list[OrderItemOut]
    payment: PaymentInstructionsOut | None = None  # the buyer, while payment is still due
    member: OrderMemberOut | None = None  # admins only


class OrderSummary(BaseModel):
    pending: int
    pending_flagged: int
    awaiting_payment: int
    approved: int
    rejected: int


class PassEventOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID
    society_name: str
    title: str
    venue: str | None
    starts_at: datetime
    ends_at: datetime
    banner_url: str | None


class PassOut(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    event: PassEventOut
    tier_id: uuid.UUID
    tier_name: str
    holder_name: str
    holder_type: str
    qr_token: str
    status: PassStatus
    valid_days: ValidDays
    valid_dates: list[date]  # empty == all event days
    scanned_dates: list[date]
    created_at: datetime
