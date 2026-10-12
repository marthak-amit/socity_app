"""Expo push notifications. Fire-and-forget: failures are logged, never raised to the request."""

import logging
import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import PushToken

log = logging.getLogger("societypass.push")


@dataclass
class PushMessage:
    user_ids: list[uuid.UUID]
    title: str
    body: str
    data: dict


class PushService:
    def __init__(self) -> None:
        self.outbox: list[PushMessage] = []  # inspected by tests

    async def send(self, user_ids: list[uuid.UUID], title: str, body: str, data: dict | None = None) -> None:
        settings = get_settings()
        msg = PushMessage(list(user_ids), title, body, data or {})
        if settings.env == "test":
            self.outbox.append(msg)
            return
        if not user_ids:
            return
        try:
            async with SessionLocal() as session:
                tokens = (
                    await session.scalars(select(PushToken.token).where(PushToken.user_id.in_(user_ids)))
                ).all()
            if not tokens:
                return
            async with httpx.AsyncClient(timeout=10) as client:
                for i in range(0, len(tokens), 100):  # Expo accepts up to 100 per request
                    chunk = tokens[i : i + 100]
                    resp = await client.post(
                        settings.expo_push_url,
                        json=[{"to": t, "title": title, "body": body, "data": msg.data, "sound": "default"} for t in chunk],
                    )
                    if resp.status_code >= 400:
                        log.warning("expo push failed: %s %s", resp.status_code, resp.text[:200])
        except Exception:  # noqa: BLE001 - notifications must never break a request
            log.exception("push send failed")


push = PushService()
