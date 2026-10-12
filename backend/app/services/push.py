"""Push notifications via Firebase Cloud Messaging (HTTP v1) for the Flutter app.

Fire-and-forget: failures are logged, never raised into a request. Providers:
  * `fcm` – production. Needs FCM_SERVICE_ACCOUNT_FILE (service-account JSON from Firebase console).
  * `log` – dev default: logs what would be sent.
Tokens FCM reports as unregistered are deleted.
"""

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import httpx
import jwt
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import PushToken

log = logging.getLogger("societypass.push")
FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


@dataclass
class PushMessage:
    user_ids: list[uuid.UUID]
    title: str
    body: str
    data: dict


class PushProvider(ABC):
    name: str

    @abstractmethod
    async def send(self, tokens: list[str], title: str, body: str, data: dict) -> list[str]:
        """Deliver to device tokens; return the tokens that are no longer valid (to be pruned)."""


class LogPushProvider(PushProvider):
    name = "log"

    async def send(self, tokens: list[str], title: str, body: str, data: dict) -> list[str]:
        log.info("push (log provider) → %d device(s): %s — %s %s", len(tokens), title, body, data)
        return []


class FcmPushProvider(PushProvider):
    """FCM HTTP v1 with a service-account OAuth token (no firebase-admin dependency)."""

    name = "fcm"

    def __init__(self, service_account_file: str, client: httpx.AsyncClient | None = None) -> None:
        self._sa = json.loads(Path(service_account_file).read_text())
        self._project = self._sa["project_id"]
        self._client = client
        self._token: tuple[str, float] | None = None

    async def _access_token(self, client: httpx.AsyncClient) -> str:
        if self._token and self._token[1] > time.time() + 60:
            return self._token[0]
        now = int(time.time())
        assertion = jwt.encode(
            {"iss": self._sa["client_email"], "scope": FCM_SCOPE, "aud": self._sa["token_uri"], "iat": now, "exp": now + 3600},
            self._sa["private_key"], algorithm="RS256",
        )
        resp = await client.post(self._sa["token_uri"], data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion})
        resp.raise_for_status()
        j = resp.json()
        self._token = (j["access_token"], time.time() + int(j.get("expires_in", 3600)))
        return self._token[0]

    async def send(self, tokens: list[str], title: str, body: str, data: dict) -> list[str]:
        invalid: list[str] = []
        own = self._client is None
        client = self._client or httpx.AsyncClient(timeout=10)
        try:
            access = await self._access_token(client)
            url = f"https://fcm.googleapis.com/v1/projects/{self._project}/messages:send"
            str_data = {k: str(v) for k, v in data.items()}  # FCM data payload values must be strings

            async def one(token: str) -> None:
                resp = await client.post(
                    url, headers={"Authorization": f"Bearer {access}"},
                    json={"message": {"token": token, "notification": {"title": title, "body": body}, "data": str_data,
                                      "android": {"priority": "high"}, "apns": {"payload": {"aps": {"sound": "default"}}}}},
                )
                if resp.status_code == 404 or (resp.status_code == 400 and "INVALID_ARGUMENT" in resp.text and "token" in resp.text.lower()):
                    invalid.append(token)
                elif resp.status_code >= 400:
                    log.warning("fcm send failed: %s %s", resp.status_code, resp.text[:200])

            await asyncio.gather(*(one(t) for t in tokens))
        finally:
            if own:
                await client.aclose()
        return invalid


def get_provider() -> PushProvider:
    s = get_settings()
    if s.push_provider == "fcm" and s.fcm_service_account_file:
        return FcmPushProvider(s.fcm_service_account_file)
    return LogPushProvider()


class PushService:
    def __init__(self) -> None:
        self.outbox: list[PushMessage] = []  # inspected by tests
        self._provider: PushProvider | None = None

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
                tokens = list((await session.scalars(select(PushToken.token).where(PushToken.user_id.in_(user_ids)))).all())
            if not tokens:
                return
            self._provider = self._provider or get_provider()
            invalid = await self._provider.send(tokens, title, body, msg.data)
            if invalid:
                async with SessionLocal() as session:
                    await session.execute(delete(PushToken).where(PushToken.token.in_(invalid)))
                    await session.commit()
        except Exception:  # noqa: BLE001 - notifications must never break a request
            log.exception("push send failed")


push = PushService()
