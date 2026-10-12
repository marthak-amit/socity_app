"""'Event tomorrow' push reminders to everyone holding an approved pass."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.core.db import SessionLocal
from app.models import Event, EventDay, Pass, Society
from app.models.enums import EventStatus, PassStatus
from app.services.events import society_tz
from app.services.push import push

log = logging.getLogger("societypass.reminders")


async def send_event_reminders(now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    sent = 0
    async with SessionLocal() as session:
        rows = (await session.execute(
            select(Event, Society).join(Society, Society.id == Event.society_id)
            .where(Event.status == EventStatus.PUBLISHED.value, Event.reminder_sent_at.is_(None),
                   Event.starts_at > now - timedelta(days=1), Event.starts_at < now + timedelta(days=3))
        )).all()
        for ev, soc in rows:
            tz = society_tz(soc)
            first_day = await session.scalar(select(EventDay.date).where(EventDay.event_id == ev.id).order_by(EventDay.date).limit(1))
            if first_day is None or first_day != (now.astimezone(tz) + timedelta(days=1)).date():
                continue
            # atomic claim → safe with several workers
            claimed = await session.scalar(
                update(Event).where(Event.id == ev.id, Event.reminder_sent_at.is_(None))
                .values(reminder_sent_at=now).returning(Event.id)
            )
            if not claimed:
                continue
            holders = (await session.scalars(
                select(Pass.user_id).where(Pass.event_id == ev.id, Pass.status == PassStatus.ACTIVE.value).distinct()
            )).all()
            await push.send(list(holders), f"Tomorrow: {ev.title}", "Keep your pass QR handy — see you there!",
                            {"type": "event_reminder", "society_id": str(ev.society_id), "event_id": str(ev.id)})
            sent += 1
        await session.commit()
    return sent
