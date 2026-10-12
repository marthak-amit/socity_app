import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

PK = dict(primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))


def created_col() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Society(Base):
    __tablename__ = "societies"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **PK)
    name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(80))
    address: Mapped[str | None] = mapped_column(Text)
    invite_code: Mapped[str] = mapped_column(String(12), unique=True)
    upi_id: Mapped[str | None] = mapped_column(String(100))
    upi_name: Mapped[str | None] = mapped_column(String(100))
    logo_key: Mapped[str | None] = mapped_column(String(255))  # (spec: logo_url) stores storage key
    status: Mapped[str] = mapped_column(String(12), default="active", server_default="active")
    timezone: Mapped[str] = mapped_column(String(40), default="Asia/Kolkata", server_default="Asia/Kolkata")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_col()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("status in ('active','suspended','deleted')", name="ck_society_status"),
        Index("ix_societies_status", "status"),
    )


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **PK)
    phone: Mapped[str] = mapped_column(String(20), unique=True)  # E.164
    name: Mapped[str | None] = mapped_column(String(120))
    avatar_key: Mapped[str | None] = mapped_column(String(255))
    locale: Mapped[str] = mapped_column(String(5), default="en", server_default="en")
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = created_col()
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OtpCode(Base):
    __tablename__ = "otp_codes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **PK)
    phone: Mapped[str] = mapped_column(String(20))
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_col()

    __table_args__ = (Index("ix_otp_phone_created", "phone", "created_at"),)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **PK)  # == JWT jti
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_col()


class PushToken(Base):
    __tablename__ = "push_tokens"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **PK)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token: Mapped[str] = mapped_column(String(200), unique=True)
    platform: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = created_col()


class Membership(Base):
    __tablename__ = "memberships"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **PK)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    society_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("societies.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(12), default="member", server_default="member")
    flat_no: Mapped[str | None] = mapped_column(String(20))
    wing: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(10), default="pending", server_default="pending")
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_col()

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    society: Mapped["Society"] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "society_id", name="uq_membership_user_society"),
        CheckConstraint("role in ('owner','admin','volunteer','member')", name="ck_membership_role"),
        CheckConstraint("status in ('pending','active','removed')", name="ck_membership_status"),
        Index("ix_memberships_society_status_role", "society_id", "status", "role"),
    )


class PreapprovedMember(Base):
    """Rows imported from an admin CSV (flat + phone) that auto-approve a join request."""

    __tablename__ = "preapproved_members"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **PK)
    society_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("societies.id", ondelete="CASCADE"))
    phone: Mapped[str] = mapped_column(String(20))
    wing: Mapped[str | None] = mapped_column(String(20))
    flat_no: Mapped[str | None] = mapped_column(String(20))
    name: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = created_col()

    __table_args__ = (UniqueConstraint("society_id", "phone", name="uq_preapproved_society_phone"),)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **PK)
    society_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("societies.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    venue: Mapped[str | None] = mapped_column(String(200))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    banner_key: Mapped[str | None] = mapped_column(String(255))  # (spec: banner_url)
    booking_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(10), default="draft", server_default="draft")
    is_paid: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    payment_provider: Mapped[str] = mapped_column(String(20), default="manual_upi", server_default="manual_upi")
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_col()

    days: Mapped[list["EventDay"]] = relationship(order_by="EventDay.date", cascade="all, delete-orphan")
    tiers: Mapped[list["PassTier"]] = relationship(order_by="PassTier.sort_order", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status in ('draft','published','closed','cancelled')", name="ck_event_status"),
        CheckConstraint("ends_at >= starts_at", name="ck_event_times"),
        Index("ix_events_society_status_starts", "society_id", "status", "starts_at"),
    )


class EventDay(Base):
    __tablename__ = "event_days"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **PK)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date)
    label: Mapped[str | None] = mapped_column(String(60))

    __table_args__ = (UniqueConstraint("event_id", "date", name="uq_event_day"),)


class PassTier(Base):
    __tablename__ = "pass_tiers"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **PK)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(String(300))
    price: Mapped[int] = mapped_column(Integer, default=0)  # whole rupees
    capacity: Mapped[int] = mapped_column(Integer)
    per_user_limit: Mapped[int] = mapped_column(Integer, default=4)
    valid_days: Mapped[str] = mapped_column(String(10), default="all", server_default="all")
    allow_guests: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    day_links: Mapped[list["PassTierDay"]] = relationship(cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_tier_price"),
        CheckConstraint("capacity >= 0", name="ck_tier_capacity"),
        CheckConstraint("per_user_limit >= 1", name="ck_tier_limit"),
        CheckConstraint("valid_days in ('all','specific')", name="ck_tier_valid_days"),
    )


class PassTierDay(Base):
    __tablename__ = "pass_tier_days"
    tier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pass_tiers.id", ondelete="CASCADE"), primary_key=True)
    event_day_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("event_days.id", ondelete="CASCADE"), primary_key=True
    )


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **PK)
    ref_code: Mapped[str] = mapped_column(String(16), unique=True)  # shown to user, used in UPI note
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    society_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("societies.id", ondelete="CASCADE"))
    total_amount: Mapped[int] = mapped_column(Integer)
    paid_amount: Mapped[int | None] = mapped_column(Integer)  # amount the member says they paid
    utr: Mapped[str | None] = mapped_column(String(32))
    screenshot_key: Mapped[str | None] = mapped_column(String(255))  # (spec: screenshot_url) private bucket
    payment_provider: Mapped[str] = mapped_column(String(20), default="manual_upi", server_default="manual_upi")
    provider_ref: Mapped[str | None] = mapped_column(String(100))
    payment_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(10), default="pending", server_default="pending")
    flags: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    reject_reason: Mapped[str | None] = mapped_column(String(300))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_col()

    items: Mapped[list["OrderItem"]] = relationship(cascade="all, delete-orphan")
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    event: Mapped["Event"] = relationship()

    __table_args__ = (
        CheckConstraint("status in ('pending','approved','rejected','cancelled')", name="ck_order_status"),
        Index("ix_orders_society_status_created", "society_id", "status", "created_at"),
        Index("ix_orders_event_status", "event_id", "status"),
        Index("ix_orders_user", "user_id", "created_at"),
        Index("ix_orders_utr", "utr"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **PK)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    tier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pass_tiers.id"), index=True)
    qty: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[int] = mapped_column(Integer)
    holders: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))

    tier: Mapped["PassTier"] = relationship()

    __table_args__ = (CheckConstraint("qty >= 1", name="ck_item_qty"),)


class Pass(Base):
    __tablename__ = "passes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **PK)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    tier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pass_tiers.id"), index=True)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    society_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("societies.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    holder_name: Mapped[str] = mapped_column(String(120))
    holder_type: Mapped[str] = mapped_column(String(10), default="member", server_default="member")
    qr_token: Mapped[str] = mapped_column(String(400), unique=True)
    status: Mapped[str] = mapped_column(String(10), default="active", server_default="active")
    created_at: Mapped[datetime] = created_col()

    tier: Mapped["PassTier"] = relationship()
    order: Mapped["Order"] = relationship()

    __table_args__ = (
        CheckConstraint("status in ('active','revoked')", name="ck_pass_status"),
        CheckConstraint("holder_type in ('member','guest')", name="ck_pass_holder_type"),
    )


class PassScan(Base):
    __tablename__ = "pass_scans"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **PK)
    pass_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("passes.id", ondelete="CASCADE"))
    event_day_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event_days.id", ondelete="CASCADE"))
    scanned_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    scanned_at: Mapped[datetime] = created_col()
    gate: Mapped[str | None] = mapped_column(String(40))
    client_ref: Mapped[str | None] = mapped_column(String(64))  # client-generated id → retry-safe scans

    __table_args__ = (
        UniqueConstraint("pass_id", "event_day_id", name="uq_scan_pass_day"),  # one scan per pass per day
        Index("ix_scans_day", "event_day_id"),
    )


class VolunteerAssignment(Base):
    __tablename__ = "volunteer_assignments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **PK)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_col()

    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_volunteer_event_user"),
        Index("ix_volunteer_user", "user_id"),
    )


class GalleryItem(Base):
    __tablename__ = "gallery_items"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **PK)
    society_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("societies.id", ondelete="CASCADE"))
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"))
    url_key: Mapped[str] = mapped_column(String(255))  # (spec: url)
    thumb_key: Mapped[str] = mapped_column(String(255))  # (spec: thumb_url)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(10), default="pending", server_default="pending")
    moderated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_col()

    uploader: Mapped["User"] = relationship(foreign_keys=[uploaded_by])

    __table_args__ = (
        CheckConstraint("status in ('pending','approved','rejected')", name="ck_gallery_status"),
        Index("ix_gallery_society_status_created", "society_id", "status", "created_at"),
        Index("ix_gallery_event_status", "event_id", "status"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    society_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("societies.id", ondelete="SET NULL"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    meta: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = created_col()

    __table_args__ = (
        Index("ix_audit_society_created", "society_id", "created_at"),
        Index("ix_audit_action", "action"),
    )


class Upload(Base):
    """Tracks presigned uploads so a storage key can only be consumed by whoever requested it."""

    __tablename__ = "uploads"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), **PK)
    key: Mapped[str] = mapped_column(String(255), unique=True)
    society_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("societies.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(String(12))
    content_type: Mapped[str] = mapped_column(String(50))
    max_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = created_col()
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
