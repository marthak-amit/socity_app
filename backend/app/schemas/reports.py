import uuid
from datetime import date

from pydantic import BaseModel


class ReportTotals(BaseModel):
    collected_amount: int
    pending_amount: int
    pending_count: int
    awaiting_payment_count: int
    approved_orders: int
    rejected_orders: int
    passes_sold: int
    passes_scanned: int  # distinct passes that entered at least once


class TierRow(BaseModel):
    tier_id: uuid.UUID
    name: str
    price: int
    capacity: int
    sold: int
    pending: int
    collected: int
    scanned: int


class WingRow(BaseModel):
    wing: str
    orders: int
    passes: int
    collected: int


class DayRow(BaseModel):
    date: date
    scanned: int
    expected: int


class EventReport(BaseModel):
    event_id: uuid.UUID
    title: str
    totals: ReportTotals
    by_tier: list[TierRow]
    by_wing: list[WingRow]
    by_day: list[DayRow]
