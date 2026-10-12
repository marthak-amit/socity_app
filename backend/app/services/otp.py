"""Pluggable OTP delivery. `console` logs the code (dev); `msg91` is a thin stub for production."""

import logging
from abc import ABC, abstractmethod

import httpx

from app.core.config import get_settings

log = logging.getLogger("societypass.otp")


class OtpProvider(ABC):
    name: str

    @abstractmethod
    async def send(self, phone: str, code: str) -> None: ...


class ConsoleOtpProvider(OtpProvider):
    name = "console"
    # Captured for tests / dev tooling: phone -> last code sent.
    last_codes: dict[str, str] = {}

    async def send(self, phone: str, code: str) -> None:
        self.last_codes[phone] = code
        log.warning("OTP for %s is %s", phone, code)


class Msg91OtpProvider(OtpProvider):
    """Stub for MSG91 (https://docs.msg91.com/otp). Configure MSG91_AUTH_KEY + MSG91_TEMPLATE_ID.

    TODO(prod): verify DLT-registered template, handle delivery webhooks and provider-side retries.
    """

    name = "msg91"

    async def send(self, phone: str, code: str) -> None:
        s = get_settings()
        if not (s.msg91_auth_key and s.msg91_template_id):
            raise RuntimeError("MSG91_AUTH_KEY / MSG91_TEMPLATE_ID not configured")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://control.msg91.com/api/v5/otp",
                params={
                    "template_id": s.msg91_template_id,
                    "mobile": phone.lstrip("+"),
                    "otp": code,
                },
                headers={"authkey": s.msg91_auth_key, "content-type": "application/json"},
                json={},
            )
            resp.raise_for_status()


_providers: dict[str, OtpProvider] = {}


def get_otp_provider() -> OtpProvider:
    name = get_settings().otp_provider
    if name not in _providers:
        _providers[name] = {"console": ConsoleOtpProvider, "msg91": Msg91OtpProvider}[name]()
    return _providers[name]
