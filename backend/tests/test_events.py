from datetime import UTC, datetime, timedelta

from PIL import Image

from app.core.db import SessionLocal
from app.services.storage import get_storage
from tests.helpers import create_society, join_and_approve, login, png_bytes, upload_image


def iso(dt: datetime) -> str:
    return dt.isoformat()


def event_body(**kw):
    start = datetime.now(UTC) + timedelta(days=5)
    body = {
        "title": "Navratri 2026", "description": "Garba nights", "venue": "Clubhouse",
        "starts_at": iso(start), "ends_at": iso(start + timedelta(hours=4)),
        "tiers": [{"name": "Family", "price": 500, "capacity": 100, "per_user_limit": 4}],
    }
    body.update(kw)
    return body


async def setup(client, upi="greenvalley@okhdfc"):
    owner, member = await login(client, "Owner"), await login(client, "Member")
    s = await create_society(owner, upi_id=upi)
    await join_and_approve(owner, member, s)
    return owner, member, s


async def test_create_event_defaults_single_day_and_draft_hidden_from_members(client):
    owner, member, s = await setup(client)
    r = await owner.post(f"/societies/{s['id']}/events", event_body())
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["status"] == "draft" and len(ev["days"]) == 1 and ev["tiers"][0]["remaining"] == 100
    assert (await member.get(f"/societies/{s['id']}/events")).json()["total"] == 0
    assert (await member.get(f"/societies/{s['id']}/events/{ev['id']}")).status_code == 404
    assert (await owner.get(f"/societies/{s['id']}/events")).json()["total"] == 1


async def test_members_cannot_create_or_modify_events(client):
    owner, member, s = await setup(client)
    base = f"/societies/{s['id']}/events"
    assert (await member.post(base, event_body())).status_code == 403
    ev = (await owner.post(base, event_body())).json()
    for call in (member.patch(f"{base}/{ev['id']}", {"title": "xx"}), member.post(f"{base}/{ev['id']}/publish"),
                 member.post(f"{base}/{ev['id']}/tiers", {"name": "VIP", "price": 1, "capacity": 1}),
                 member.delete(f"{base}/{ev['id']}")):
        assert (await call).status_code == 403


async def test_nine_day_event_with_specific_day_tier(client):
    owner, member, s = await setup(client)
    start = datetime.now(UTC).replace(hour=8, minute=0) + timedelta(days=10)
    body = event_body(
        title="Navratri", starts_at=iso(start), ends_at=iso(start + timedelta(days=8, hours=8)),
        tiers=[
            {"name": "Season Pass", "price": 1500, "capacity": 200, "per_user_limit": 5},
            {"name": "Ashtami Special", "price": 300, "capacity": 50, "valid_days": "specific",
             "day_dates": [(start + timedelta(days=7)).date().isoformat()]},
        ],
    )
    r = await owner.post(f"/societies/{s['id']}/events", body)
    assert r.status_code == 201, r.text
    ev = r.json()
    assert len(ev["days"]) == 9
    special = next(t for t in ev["tiers"] if t["name"] == "Ashtami Special")
    assert special["valid_days"] == "specific" and len(special["day_ids"]) == 1


async def test_tier_day_outside_event_rejected(client):
    owner, _, s = await setup(client)
    body = event_body(tiers=[{"name": "X", "price": 1, "capacity": 1, "valid_days": "specific", "day_dates": ["2020-01-01"]}])
    assert (await owner.post(f"/societies/{s['id']}/events", body)).status_code == 400


async def test_time_validation(client):
    owner, _, s = await setup(client)
    start = datetime.now(UTC) + timedelta(days=1)
    r = await owner.post(f"/societies/{s['id']}/events", event_body(starts_at=iso(start), ends_at=iso(start - timedelta(hours=1))))
    assert r.status_code == 422


async def test_free_event_rejects_priced_tiers(client):
    owner, _, s = await setup(client)
    r = await owner.post(f"/societies/{s['id']}/events", event_body(is_paid=False))
    assert r.status_code == 400 and r.json()["detail"]["code"] == "free_event_price"
    ok = event_body(is_paid=False, tiers=[{"name": "Free entry", "price": 0, "capacity": 50}])
    assert (await owner.post(f"/societies/{s['id']}/events", ok)).status_code == 201


async def test_publish_rules_and_visibility_and_push(client):
    from app.services.push import push

    owner, member, s = await setup(client)
    base = f"/societies/{s['id']}/events"
    empty = (await owner.post(base, event_body(tiers=[]))).json()
    r = await owner.post(f"{base}/{empty['id']}/publish")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "no_tiers"
    ev = (await owner.post(base, event_body())).json()
    r = await owner.post(f"{base}/{ev['id']}/publish")
    assert r.status_code == 200 and r.json()["status"] == "published" and r.json()["booking_open"] is True
    assert (await owner.post(f"{base}/{ev['id']}/publish")).status_code == 409
    got = (await member.get(f"{base}?when=upcoming")).json()
    assert got["total"] == 1 and got["items"][0]["tiers"][0]["remaining"] == 100
    assert any(m.data.get("type") == "event_published" for m in push.outbox)


async def test_paid_event_needs_upi_to_publish(client):
    owner, _, s = await setup(client, upi=None)
    ev = (await owner.post(f"/societies/{s['id']}/events", event_body())).json()
    r = await owner.post(f"/societies/{s['id']}/events/{ev['id']}/publish")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "upi_not_configured"


async def test_close_reopen_cancel_and_delete(client):
    owner, member, s = await setup(client)
    base = f"/societies/{s['id']}/events"
    ev = (await owner.post(base, event_body())).json()
    await owner.post(f"{base}/{ev['id']}/publish")
    assert (await owner.post(f"{base}/{ev['id']}/close")).json()["booking_open"] is False
    assert (await owner.post(f"{base}/{ev['id']}/reopen")).json()["status"] == "published"
    assert (await owner.post(f"{base}/{ev['id']}/cancel")).json()["status"] == "cancelled"
    assert (await owner.patch(f"{base}/{ev['id']}", {"title": "xx"})).status_code == 409
    draft = (await owner.post(base, event_body())).json()
    assert (await owner.delete(f"{base}/{draft['id']}")).status_code == 200
    assert (await owner.get(f"{base}/{draft['id']}")).status_code == 404


async def test_update_event_and_tier_changes(client):
    owner, _, s = await setup(client)
    base = f"/societies/{s['id']}/events"
    ev = (await owner.post(base, event_body())).json()
    r = await owner.patch(f"{base}/{ev['id']}", {"title": "Navratri Mahotsav", "venue": "Main lawn"})
    assert r.json()["title"] == "Navratri Mahotsav" and r.json()["venue"] == "Main lawn"
    tid = ev["tiers"][0]["id"]
    r = await owner.patch(f"{base}/{ev['id']}/tiers/{tid}", {"price": 600, "capacity": 80})
    assert r.status_code == 200 and r.json()["price"] == 600 and r.json()["remaining"] == 80
    r = await owner.post(f"{base}/{ev['id']}/tiers", {"name": "VIP", "price": 2000, "capacity": 10})
    assert r.status_code == 201
    assert (await owner.delete(f"{base}/{ev['id']}/tiers/{r.json()['id']}")).status_code == 200
    d = await owner.post(f"{base}/{ev['id']}/days", {"date": (datetime.now(UTC) + timedelta(days=6)).date().isoformat(), "label": "Day 2"})
    assert d.status_code == 201
    assert len((await owner.get(f"{base}/{ev['id']}")).json()["days"]) == 2


async def test_volunteer_assignment_sets_role_and_expiry(client):
    owner, member, s = await setup(client)
    base = f"/societies/{s['id']}/events"
    ev = (await owner.post(base, event_body())).json()
    r = await owner.post(f"{base}/{ev['id']}/volunteers", {"user_id": member.id})
    assert r.status_code == 201
    exp = datetime.fromisoformat(r.json()["expires_at"])
    assert exp > datetime.fromisoformat(ev["ends_at"])
    me = (await member.get("/me")).json()
    assert me["memberships"][0]["role"] == "volunteer"
    assert (await member.get(f"{base}/{ev['id']}/volunteers")).status_code == 403  # volunteers can't manage volunteers
    outsider = await login(client, "Outsider")
    assert (await owner.post(f"{base}/{ev['id']}/volunteers", {"user_id": outsider.id})).status_code == 404
    # moving the event end moves the assignment expiry
    new_end = datetime.fromisoformat(ev["ends_at"]) + timedelta(days=2)
    await owner.patch(f"{base}/{ev['id']}", {"ends_at": iso(new_end)})
    v = (await owner.get(f"{base}/{ev['id']}/volunteers")).json()[0]
    assert datetime.fromisoformat(v["expires_at"]) > new_end


# ------------------------------------------------------------------------------------------- uploads
async def test_banner_upload_flow_strips_exif_and_serves_public_url(client):
    owner, _, s = await setup(client)
    data = png_bytes((3000, 2000), exif=True, fmt="JPEG")
    up = await upload_image(owner, s["id"], "banner", data, "image/jpeg")
    r = await owner.post(f"/societies/{s['id']}/events", event_body(banner_upload_id=up))
    assert r.status_code == 201, r.text
    url = r.json()["banner_url"]
    assert url and "/public/" in url
    key = url.split("/files/")[1]
    stored = await get_storage().get_object(key)
    import io
    img = Image.open(io.BytesIO(stored))
    assert max(img.size) <= 1600 and not img.getexif()
    assert (await client.get(url)).status_code == 200
    # an upload id is single-use
    assert (await owner.post(f"/societies/{s['id']}/events", event_body(banner_upload_id=up))).status_code == 404


async def test_upload_validation(client):
    owner, member, s = await setup(client)
    base = f"/societies/{s['id']}/uploads/presign"
    assert (await owner.post(base, {"purpose": "banner", "content_type": "application/pdf", "size": 100})).status_code == 400
    assert (await owner.post(base, {"purpose": "banner", "content_type": "image/png", "size": 50 * 1024 * 1024})).status_code == 400
    assert (await owner.post(base, {"purpose": "screenshot", "content_type": "image/png", "size": 6 * 1024 * 1024})).status_code == 400
    assert (await member.post(base, {"purpose": "banner", "content_type": "image/png", "size": 100})).status_code == 403
    # content-type lies: a text file declared as PNG fails server-side validation
    up = await upload_image(owner, s["id"], "banner", b"this is not an image", "image/png")
    r = await owner.post(f"/societies/{s['id']}/events", event_body(banner_upload_id=up))
    assert r.status_code == 400 and r.json()["detail"]["code"] == "invalid_image"


async def test_upload_cannot_be_used_by_other_user_or_society(client):
    owner, member, s = await setup(client)
    other_owner = await login(client, "Other")
    s2 = await create_society(other_owner, "Other Society")
    up = await upload_image(owner, s["id"], "banner")
    # same id presented in another society / by another user → not found
    assert (await other_owner.post(f"/societies/{s2['id']}/events", event_body(banner_upload_id=up))).status_code == 404
    other_admin_of_s = await login(client, "Admin2")
    await join_and_approve(owner, other_admin_of_s, s, role="admin")
    assert (await other_admin_of_s.post(f"/societies/{s['id']}/events", event_body(banner_upload_id=up))).status_code == 404


async def test_signed_local_urls_reject_tampering(client):
    owner, _, s = await setup(client)
    r = await owner.post(f"/societies/{s['id']}/uploads/presign", {"purpose": "banner", "content_type": "image/png", "size": 100})
    url = r.json()["upload_url"]
    bad = url.replace("sig=", "sig=00")
    assert (await client.put(bad, content=b"x")).status_code == 403


async def test_event_reminder_job(client):
    from app.services.reminders import send_event_reminders

    owner, _, s = await setup(client)
    start = datetime.now(UTC) + timedelta(hours=26)
    ev = (await owner.post(f"/societies/{s['id']}/events", event_body(starts_at=iso(start), ends_at=iso(start + timedelta(hours=3))))).json()
    await owner.post(f"/societies/{s['id']}/events/{ev['id']}/publish")
    # nobody holds passes yet → job claims the event but there's no one to notify; second run is a no-op
    first = await send_event_reminders()
    second = await send_event_reminders()
    assert first + second <= 1 and second == 0
    _ = SessionLocal
