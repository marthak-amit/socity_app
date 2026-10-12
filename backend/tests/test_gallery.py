import io
from datetime import UTC, datetime, timedelta

from PIL import Image

from app.services.storage import get_storage
from tests.helpers import create_society, join_and_approve, login, png_bytes, upload_image
from tests.test_events import event_body, iso


async def setup(client):
    owner, member, other = await login(client, "Owner"), await login(client, "Meera"), await login(client, "Raj")
    s = await create_society(owner)
    await join_and_approve(owner, member, s)
    await join_and_approve(owner, other, s)
    return owner, member, other, s


def gal(s):
    return f"/societies/{s['id']}/gallery"


async def test_admin_upload_is_auto_approved_with_thumbnail_and_no_exif(client):
    owner, member, _, s = await setup(client)
    raw = png_bytes((4000, 3000), exif=True, fmt="JPEG")
    up = await upload_image(owner, s["id"], "gallery", raw, "image/jpeg")
    r = await owner.post(gal(s), {"upload_ids": [up]})
    assert r.status_code == 201, r.text
    item = r.json()[0]
    assert item["status"] == "approved" and item["mine"] is True
    full = await client.get(item["url"])
    thumb = await client.get(item["thumb_url"])
    assert full.status_code == 200 and thumb.status_code == 200 and len(thumb.content) < len(full.content)
    fi, ti = Image.open(io.BytesIO(full.content)), Image.open(io.BytesIO(thumb.content))
    assert max(fi.size) == 2048 and max(ti.size) == 480
    assert not fi.getexif() and not ti.getexif()                     # GPS / camera tags are gone
    assert b"SecretCameraMaker" not in full.content and b"Exif" not in full.content[:64]
    # the raw upload is deleted after processing
    assert (await get_storage().object_size(f"private/raw/{up}")) is None
    # members see it right away
    assert (await member.get(gal(s))).json()["total"] == 1


async def test_member_upload_needs_moderation(client):
    owner, member, other, s = await setup(client)
    up = await upload_image(member, s["id"], "gallery")
    item = (await member.post(gal(s), {"upload_ids": [up]})).json()[0]
    assert item["status"] == "pending"
    assert (await other.get(gal(s))).json()["total"] == 0                # others don't see it
    assert (await member.get(gal(s))).json()["total"] == 0               # public list is approved-only...
    mine = (await member.get(gal(s) + "?mine=true")).json()
    assert mine["total"] == 1 and mine["items"][0]["status"] == "pending"  # ...but they can see their own
    assert (await other.get(gal(s) + "?status=pending")).status_code == 403
    queue = (await owner.get(gal(s) + "?status=pending")).json()
    assert queue["total"] == 1 and queue["items"][0]["uploaded_by"]["name"] == "Meera"
    assert (await member.post(f"{gal(s)}/{item['id']}/approve")).status_code == 403
    assert (await owner.post(f"{gal(s)}/{item['id']}/approve")).json()["status"] == "approved"
    assert (await other.get(gal(s))).json()["total"] == 1
    assert (await owner.post(f"{gal(s)}/{item['id']}/approve")).status_code == 409


async def test_reject_hides_photo_and_is_audited(client):
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models import AuditLog

    owner, member, other, s = await setup(client)
    item = (await member.post(gal(s), {"upload_ids": [await upload_image(member, s["id"], "gallery")]})).json()[0]
    assert (await owner.post(f"{gal(s)}/{item['id']}/reject")).json()["status"] == "rejected"
    assert (await other.get(gal(s))).json()["total"] == 0
    assert (await owner.get(gal(s) + "?status=rejected")).json()["total"] == 1
    async with SessionLocal() as db:
        assert "gallery.rejected" in (await db.scalars(select(AuditLog.action))).all()


async def test_event_gallery_opens_after_event_ends(client):
    owner, member, _, s = await setup(client)
    past_start = datetime.now(UTC) - timedelta(days=2)
    soon = datetime.now(UTC) + timedelta(days=2)
    ev_future = (await owner.post(f"/societies/{s['id']}/events", event_body(starts_at=iso(soon), ends_at=iso(soon + timedelta(hours=3))))).json()
    ev_past = (await owner.post(f"/societies/{s['id']}/events", event_body(starts_at=iso(past_start), ends_at=iso(past_start + timedelta(hours=3))))).json()
    for ev in (ev_future, ev_past):
        up = await upload_image(owner, s["id"], "gallery")
        assert (await owner.post(gal(s), {"event_id": ev["id"], "upload_ids": [up]})).status_code == 201
    g = lambda ev: f"{gal(s)}?event_id={ev['id']}"   # noqa: E731
    assert (await member.get(g(ev_future))).json()["total"] == 0          # not over yet → locked for members
    assert (await owner.get(g(ev_future))).json()["total"] == 1           # admins can always see
    assert (await member.get(g(ev_past))).json()["total"] == 1
    assert (await member.get(gal(s))).json()["total"] == 2                # society-wide gallery has everything approved


async def test_upload_validation_and_foreign_event(client):
    owner, member, _, s = await setup(client)
    bad = await upload_image(member, s["id"], "gallery", b"%PDF-1.4 not an image", "image/jpeg")
    assert (await member.post(gal(s), {"upload_ids": [bad]})).status_code == 400
    import uuid
    ok = await upload_image(member, s["id"], "gallery")
    assert (await member.post(gal(s), {"event_id": str(uuid.uuid4()), "upload_ids": [ok]})).status_code == 404
    assert (await member.post(gal(s), {"upload_ids": []})).status_code == 422
    # a missing (never uploaded) upload id
    r = await member.post(f"/societies/{s['id']}/uploads/presign", {"purpose": "gallery", "content_type": "image/png", "size": 10})
    assert (await member.post(gal(s), {"upload_ids": [r.json()["upload_id"]]})).status_code == 400


async def test_delete_rules(client):
    owner, member, other, s = await setup(client)
    mine = (await member.post(gal(s), {"upload_ids": [await upload_image(member, s["id"], "gallery")]})).json()[0]
    assert (await other.delete(f"{gal(s)}/{mine['id']}")).status_code == 404            # someone else's photo
    assert (await member.delete(f"{gal(s)}/{mine['id']}")).status_code == 200            # own photo
    theirs = (await member.post(gal(s), {"upload_ids": [await upload_image(member, s["id"], "gallery")]})).json()[0]
    assert (await owner.delete(f"{gal(s)}/{theirs['id']}")).status_code == 200           # admin moderation
    key = theirs["url"].split("/files/")[1]
    assert (await get_storage().object_size(key)) is None
    assert (await owner.get(gal(s) + "?status=pending")).json()["total"] == 0


async def test_pagination(client):
    owner, _, _, s = await setup(client)
    ups = [await upload_image(owner, s["id"], "gallery", png_bytes(color=(i * 10, 0, 0))) for i in range(5)]
    await owner.post(gal(s), {"upload_ids": ups})
    page1 = (await owner.get(gal(s) + "?limit=2")).json()
    page3 = (await owner.get(gal(s) + "?limit=2&offset=4")).json()
    assert page1["total"] == 5 and len(page1["items"]) == 2 and len(page3["items"]) == 1
