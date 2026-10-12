"""Test helpers that drive the real HTTP API (no DB shortcuts) so tests double as flow documentation."""

import io
import itertools
import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from PIL import Image

from app.core.phone import normalize_phone
from app.services.otp import ConsoleOtpProvider

_phone_seq = itertools.count(1)


def next_phone() -> str:
    return f"+9198{next(_phone_seq):08d}"


class Actor:
    def __init__(self, client: AsyncClient, phone: str, tokens: dict, user: dict):
        self.client, self.phone, self.tokens, self.user = client, phone, tokens, user

    @property
    def id(self) -> str:
        return self.user["id"]

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.tokens['access_token']}"}

    def _h(self, kw: dict) -> dict:
        return {**self.headers, **kw.pop("headers", {})}

    async def get(self, url, **kw):
        return await self.client.get(f"/api/v1{url}", headers=self._h(kw), **kw)

    async def post(self, url, json=None, **kw):
        return await self.client.post(f"/api/v1{url}", headers=self._h(kw), json=json, **kw)

    async def patch(self, url, json=None, **kw):
        return await self.client.patch(f"/api/v1{url}", headers=self._h(kw), json=json, **kw)

    async def delete(self, url, json=None, **kw):
        return await self.client.request("DELETE", f"/api/v1{url}", headers=self._h(kw), json=json, **kw)


async def login(client: AsyncClient, name: str = "Test User", phone: str | None = None) -> Actor:
    phone = phone or next_phone()
    r = await client.post("/api/v1/auth/otp/request", json={"phone": phone})
    assert r.status_code == 200, r.text
    code = ConsoleOtpProvider.last_codes[normalize_phone(phone)]
    r = await client.post("/api/v1/auth/otp/verify", json={"phone": phone, "code": code})
    assert r.status_code == 200, r.text
    tokens = r.json()
    actor = Actor(client, phone, tokens, tokens["user"])
    if name:
        r = await actor.patch("/me", {"name": name})
        assert r.status_code == 200, r.text
        actor.user = r.json()["user"]
    return actor


async def create_society(owner: Actor, name: str = "Green Valley", upi_id: str | None = "greenvalley@okhdfc", **kw) -> dict:
    r = await owner.post("/societies", {"name": name, "city": "Ahmedabad", "upi_id": upi_id, "upi_name": name, **kw})
    assert r.status_code == 201, r.text
    return r.json()


async def join_and_approve(admin: Actor, member: Actor, society: dict, role: str = "member", wing="A", flat="101") -> str:
    r = await member.post("/societies/join", {"invite_code": society["invite_code"], "wing": wing, "flat_no": flat})
    assert r.status_code == 201, r.text
    mid = r.json()["id"]
    r = await admin.post(f"/societies/{society['id']}/members/{mid}/approve")
    assert r.status_code == 200, r.text
    if role != "member":
        r = await admin.patch(f"/societies/{society['id']}/members/{mid}", {"role": role})
        assert r.status_code == 200, r.text
    return mid


def png_bytes(size=(64, 48), color=(200, 30, 30), exif: bool = False, fmt="PNG") -> bytes:
    img = Image.new("RGB", size, color)
    out = io.BytesIO()
    kwargs = {}
    if exif:
        ex = Image.Exif()
        ex[0x010F] = "SecretCameraMaker"
        ex[0x8825] = {1: "N", 2: (23.0, 1.0, 1.0)}  # GPS IFD
        kwargs["exif"] = ex
    img.save(out, format=fmt, **kwargs)
    return out.getvalue()


async def upload_image(actor: Actor, society_id: str, purpose: str, data: bytes | None = None, content_type="image/png") -> str:
    """Full presign → PUT flow; returns upload_id."""
    data = data or png_bytes()
    r = await actor.post(f"/societies/{society_id}/uploads/presign", {"purpose": purpose, "content_type": content_type, "size": len(data)})
    assert r.status_code == 200, r.text
    p = r.json()
    put = await actor.client.put(p["upload_url"], content=data, headers=p["headers"])
    assert put.status_code == 200, put.text
    return p["upload_id"]


def future(days=0, hours=0) -> str:
    return (datetime.now(UTC) + timedelta(days=days, hours=hours)).isoformat()


def uid() -> str:
    return str(uuid.uuid4())
