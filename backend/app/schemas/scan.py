import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class ScanIn(BaseModel):
    qr_token: str = Field(min_length=1, max_length=2000)
    gate: str | None = Field(None, max_length=40)
    client_ref: str | None = Field(None, max_length=64, description="Client-generated id; makes retries idempotent")


class Counters(BaseModel):
    sold: int
    scanned_today: int
    expected_today: int


class ScanOut(BaseModel):
    ok: bool  # green (True) / red (False)
    result: str  # ok | already_scanned | invalid_token | wrong_event | pass_revoked | event_not_active | not_event_day | tier_not_valid_today
    message: str
    holder_name: str | None = None
    holder_type: str | None = None
    tier_name: str | None = None
    pass_id: uuid.UUID | None = None
    scanned_at: datetime | None = None
    scanned_by: str | None = None
    day: date | None = None
    counters: Counters


class DayStat(BaseModel):
    day_id: uuid.UUID
    date: date
    label: str | None
    scanned: int
    expected: int


class TierScanStat(BaseModel):
    tier_id: uuid.UUID
    name: str
    sold: int
    scanned_today: int


class ScanStats(BaseModel):
    sold: int
    today: DayStat | None
    days: list[DayStat]
    by_tier: list[TierScanStat]


class ScanEventOut(BaseModel):
    event_id: uuid.UUID
    title: str
    venue: str | None
    starts_at: datetime
    ends_at: datetime
    day: date | None
    counters: Counters


class RecentScan(BaseModel):
    id: uuid.UUID
    holder_name: str
    tier_name: str
    scanned_at: datetime
    scanned_by: str | None
    gate: str | None
