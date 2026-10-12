import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import EventStatus, ValidDays


class DayIn(BaseModel):
    date: date
    label: str | None = Field(None, max_length=60)


class DayOut(BaseModel):
    id: uuid.UUID
    date: date
    label: str | None


class TierIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(None, max_length=300)
    price: int = Field(0, ge=0, le=1_000_000)  # whole rupees
    capacity: int = Field(ge=0, le=100_000)
    per_user_limit: int = Field(4, ge=1, le=50)
    valid_days: ValidDays = ValidDays.ALL
    day_dates: list[date] = []  # required when valid_days == specific
    allow_guests: bool = True
    sort_order: int = 0

    @model_validator(mode="after")
    def _days(self):
        if self.valid_days == ValidDays.SPECIFIC and not self.day_dates:
            raise ValueError("day_dates required when valid_days is 'specific'")
        return self


class TierUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    description: str | None = Field(None, max_length=300)
    price: int | None = Field(None, ge=0, le=1_000_000)
    capacity: int | None = Field(None, ge=0, le=100_000)
    per_user_limit: int | None = Field(None, ge=1, le=50)
    valid_days: ValidDays | None = None
    day_dates: list[date] | None = None
    allow_guests: bool | None = None
    sort_order: int | None = None


class TierOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    price: int
    capacity: int
    per_user_limit: int
    valid_days: ValidDays
    day_ids: list[uuid.UUID]
    allow_guests: bool
    sort_order: int
    sold: int  # approved
    pending: int  # reserved by orders awaiting review
    remaining: int


class EventCreate(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    description: str | None = Field(None, max_length=5000)
    venue: str | None = Field(None, max_length=200)
    starts_at: datetime
    ends_at: datetime
    booking_deadline: datetime | None = None
    is_paid: bool = True
    payment_provider: str = "manual_upi"
    banner_upload_id: uuid.UUID | None = None
    days: list[DayIn] | None = None  # default: one day per calendar date from start to end
    tiers: list[TierIn] = []

    @model_validator(mode="after")
    def _times(self):
        if self.ends_at < self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if self.booking_deadline and self.booking_deadline > self.ends_at:
            raise ValueError("booking_deadline must be before the event ends")
        return self


class EventUpdate(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=160)
    description: str | None = Field(None, max_length=5000)
    venue: str | None = Field(None, max_length=200)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    booking_deadline: datetime | None = None
    clear_booking_deadline: bool = False
    banner_upload_id: uuid.UUID | None = None


class EventOut(BaseModel):
    id: uuid.UUID
    society_id: uuid.UUID
    title: str
    description: str | None
    venue: str | None
    starts_at: datetime
    ends_at: datetime
    banner_url: str | None
    booking_deadline: datetime | None
    status: EventStatus
    is_paid: bool
    payment_provider: str
    days: list[DayOut]
    tiers: list[TierOut]
    booking_open: bool
    is_over: bool
    created_at: datetime


class VolunteerIn(BaseModel):
    user_id: uuid.UUID


class VolunteerOut(BaseModel):
    user_id: uuid.UUID
    name: str | None
    phone: str
    expires_at: datetime
    active: bool
