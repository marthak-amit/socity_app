import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from app.core.db import SessionLocal
from app.models import Pass, VolunteerAssignment
from tests.flow import buy_and_approve, live_world
from tests.helpers import create_society, join_and_approve, login


def scan_url(w, ev=None):
    return f"/societies/{w['s']['id']}/events/{(ev or w['ev'])['id']}/scan"


async def test_scan_flow_green_then_red_with_live_counters(client):
    w = await live_world(client)
    _, passes = await buy_and_approve(w["buyer"], w["owner"], w["s"], w["ev"], w["tiers"]["Family"], 2,
                                      [{"name": "Meera", "type": "member"}, {"name": "Guest Anil", "type": "guest"}])
    p1, p2 = passes
    r = await w["vol"].post(scan_url(w), {"qr_token": p1["qr_token"], "gate": "Gate 1"})
    out = r.json()
    assert r.status_code == 200 and out["ok"] is True and out["result"] == "ok"
    assert out["holder_name"] == p1["holder_name"] and out["tier_name"] == "Family"
    assert out["counters"] == {"sold": 2, "scanned_today": 1, "expected_today": 2}
    # same code again → red, original scan time, counters unchanged (idempotent)
    out2 = (await w["vol"].post(scan_url(w), {"qr_token": p1["qr_token"]})).json()
    assert out2["ok"] is False and out2["result"] == "already_scanned" and out2["scanned_by"] == "Gate Volunteer"
    assert out2["counters"]["scanned_today"] == 1
    # the other pass is still fresh
    assert (await w["vol"].post(scan_url(w), {"qr_token": p2["qr_token"]})).json()["counters"]["scanned_today"] == 2
    stats = (await w["vol"].get(f"/societies/{w['s']['id']}/events/{w['ev']['id']}/scan-stats")).json()
    assert stats["sold"] == 2 and stats["today"]["scanned"] == 2 and next(t for t in stats["by_tier"] if t["name"] == "Family")["scanned_today"] == 2
    recent = (await w["vol"].get(f"/societies/{w['s']['id']}/events/{w['ev']['id']}/scans")).json()
    assert recent["total"] == 2 and recent["items"][0]["gate"] is None
    # the pass shows as used in the owner's app
    mine = (await w["buyer"].get(f"/societies/{w['s']['id']}/passes/mine")).json()["items"]
    assert all(len(p["scanned_dates"]) == 1 for p in mine)


async def test_client_ref_makes_retries_idempotent(client):
    w = await live_world(client)
    _, passes = await buy_and_approve(w["buyer"], w["owner"], w["s"], w["ev"], w["tiers"]["Solo"], 1)
    tok = passes[0]["qr_token"]
    a = (await w["vol"].post(scan_url(w), {"qr_token": tok, "client_ref": "abc-1"})).json()
    b = (await w["vol"].post(scan_url(w), {"qr_token": tok, "client_ref": "abc-1"})).json()   # network retry
    c = (await w["vol"].post(scan_url(w), {"qr_token": tok, "client_ref": "abc-2"})).json()   # a genuine second scan
    assert (a["ok"], b["ok"], c["ok"]) == (True, True, False)
    assert c["counters"]["scanned_today"] == 1


async def test_concurrent_scans_admit_exactly_once(client):
    w = await live_world(client)
    _, passes = await buy_and_approve(w["buyer"], w["owner"], w["s"], w["ev"], w["tiers"]["Solo"], 1)
    rs = await asyncio.gather(*[w["vol"].post(scan_url(w), {"qr_token": passes[0]["qr_token"]}) for _ in range(6)])
    assert sorted(r.json()["result"] for r in rs).count("ok") == 1


async def test_forged_tampered_and_foreign_tokens_are_red(client):
    w = await live_world(client)
    _, passes = await buy_and_approve(w["buyer"], w["owner"], w["s"], w["ev"], w["tiers"]["Solo"], 1)
    tok = passes[0]["qr_token"]
    v, body, sig = tok.split(".")
    for bad in ["garbage", f"{v}.{body}.{sig[:-2]}AA", f"{v}.{body[:-2]}AA.{sig}", f"v2.{body}.{sig}", f"{v}.{body}"]:
        out = (await w["vol"].post(scan_url(w), {"qr_token": bad})).json()
        assert out["ok"] is False and out["result"] == "invalid_token", bad
    # a genuine pass from ANOTHER society is rejected exactly like a forgery here
    owner_b, buyer_b = await login(client, "Owner B"), await login(client, "Buyer B")
    sb = await create_society(owner_b, "Society B", upi_id="b@okicici")
    await join_and_approve(owner_b, buyer_b, sb)
    from tests.test_events import event_body
    evb = (await owner_b.post(f"/societies/{sb['id']}/events", event_body(
        starts_at=w["ev"]["starts_at"], ends_at=w["ev"]["ends_at"]))).json()
    await owner_b.post(f"/societies/{sb['id']}/events/{evb['id']}/publish")
    _, pb = await buy_and_approve(buyer_b, owner_b, sb, evb, evb["tiers"][0], 1)
    out = (await w["vol"].post(scan_url(w), {"qr_token": pb[0]["qr_token"]})).json()
    assert out["result"] == "invalid_token"
    # and society B's scanner can't be used against society A's event
    assert (await owner_b.post(scan_url(w), {"qr_token": tok})).status_code == 404


async def test_pass_for_different_event_is_wrong_event(client):
    w = await live_world(client)
    from tests.test_events import event_body
    ev2 = (await w["owner"].post(f"/societies/{w['s']['id']}/events", event_body(
        title="Second Event", starts_at=w["ev"]["starts_at"], ends_at=w["ev"]["ends_at"]))).json()
    await w["owner"].post(f"/societies/{w['s']['id']}/events/{ev2['id']}/publish")
    _, passes = await buy_and_approve(w["buyer"], w["owner"], w["s"], ev2, ev2["tiers"][0], 1)
    out = (await w["owner"].post(scan_url(w), {"qr_token": passes[0]["qr_token"]})).json()
    assert out["result"] == "wrong_event" and "Second Event" in out["message"] and out["ok"] is False


async def test_scanner_authorization(client):
    w = await live_world(client)
    _, passes = await buy_and_approve(w["buyer"], w["owner"], w["s"], w["ev"], w["tiers"]["Solo"], 1)
    tok = passes[0]["qr_token"]
    assert (await w["buyer"].post(scan_url(w), {"qr_token": tok})).status_code == 403          # plain member
    # a volunteer NOT assigned to this event
    other = await login(client, "Other Vol")
    await join_and_approve(w["owner"], other, w["s"], role="volunteer")
    r = await other.post(scan_url(w), {"qr_token": tok})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "not_assigned"
    assert (await other.get(f"/societies/{w['s']['id']}/events/{w['ev']['id']}/scan-stats")).status_code == 403
    assert (await other.get(f"/societies/{w['s']['id']}/scan/events")).json() == []
    # assigned volunteer sees it; after the assignment expires scanning stops
    assert [e["title"] for e in (await w["vol"].get(f"/societies/{w['s']['id']}/scan/events")).json()] == ["Navratri 2026"]
    async with SessionLocal() as db:
        await db.execute(update(VolunteerAssignment).values(expires_at=datetime.now(UTC) - timedelta(minutes=1)))
        await db.commit()
    r = await w["vol"].post(scan_url(w), {"qr_token": tok})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "assignment_expired"
    assert (await w["vol"].get(f"/societies/{w['s']['id']}/scan/events")).json() == []
    # admins/owners always can
    assert (await w["owner"].post(scan_url(w), {"qr_token": tok})).json()["ok"] is True


async def test_revoked_pass_and_cancelled_event_are_red(client):
    w = await live_world(client)
    _, passes = await buy_and_approve(w["buyer"], w["owner"], w["s"], w["ev"], w["tiers"]["Solo"], 2)
    await w["owner"].post(f"/societies/{w['s']['id']}/passes/{passes[0]['id']}/revoke")
    out = (await w["vol"].post(scan_url(w), {"qr_token": passes[0]["qr_token"]})).json()
    assert out["result"] == "pass_revoked" and out["ok"] is False
    assert (await w["vol"].get(f"/societies/{w['s']['id']}/events/{w['ev']['id']}/scan-stats")).json()["sold"] == 1
    await w["owner"].post(f"/societies/{w['s']['id']}/events/{w['ev']['id']}/cancel")
    assert (await w["vol"].post(scan_url(w), {"qr_token": passes[1]["qr_token"]})).json()["result"] == "event_not_active"


async def test_not_an_event_day(client):
    w = await live_world(client)
    start = datetime.now(UTC) + timedelta(days=5)
    from tests.test_events import event_body, iso
    ev = (await w["owner"].post(f"/societies/{w['s']['id']}/events", event_body(starts_at=iso(start), ends_at=iso(start + timedelta(hours=3))))).json()
    await w["owner"].post(f"/societies/{w['s']['id']}/events/{ev['id']}/publish")
    _, passes = await buy_and_approve(w["buyer"], w["owner"], w["s"], ev, ev["tiers"][0], 1)
    out = (await w["owner"].post(scan_url(w, ev), {"qr_token": passes[0]["qr_token"]})).json()
    assert out["result"] == "not_event_day" and out["counters"]["expected_today"] == 0


class _Clock:
    """Shift 'now' inside the scanning service to simulate later days of a multi-day event."""

    def __init__(self, monkeypatch, offset: timedelta):
        import app.services.scanning as mod
        real = mod.datetime

        class Fake(real):
            @classmethod
            def now(cls, tz=None):
                return real.now(tz) + offset

        monkeypatch.setattr(mod, "datetime", Fake)


async def test_multi_day_one_scan_per_day_and_specific_day_tiers(client, monkeypatch):
    start_day2 = None
    w = await live_world(client, days=3, tiers=[{"name": "Season", "price": 900, "capacity": 20, "per_user_limit": 4}])
    start_day2 = w["ev"]["days"][1]["date"] and datetime.fromisoformat(w["ev"]["days"][1]["date"]).date()
    r = await w["owner"].post(f"/societies/{w['s']['id']}/events/{w['ev']['id']}/tiers", {
        "name": "Day-2 only", "price": 300, "capacity": 20, "valid_days": "specific", "day_dates": [start_day2.isoformat()]})
    assert r.status_code == 201, r.text
    ev = (await w["owner"].get(f"/societies/{w['s']['id']}/events/{w['ev']['id']}")).json()
    tiers = {t["name"]: t for t in ev["tiers"]}
    _, season = await buy_and_approve(w["buyer"], w["owner"], w["s"], ev, tiers["Season"], 1)
    _, day2 = await buy_and_approve(w["buyer2"], w["owner"], w["s"], ev, tiers["Day-2 only"], 1, utr="100000000002")
    assert day2[0]["valid_days"] == "specific" and [str(d) for d in day2[0]["valid_dates"]] == [start_day2.isoformat()]

    s1 = (await w["vol"].post(scan_url(w), {"qr_token": season[0]["qr_token"]})).json()
    assert s1["ok"] and s1["counters"]["expected_today"] == 1                                    # day-2 tier not expected today
    assert (await w["vol"].post(scan_url(w), {"qr_token": season[0]["qr_token"]})).json()["result"] == "already_scanned"
    assert (await w["vol"].post(scan_url(w), {"qr_token": day2[0]["qr_token"]})).json()["result"] == "tier_not_valid_today"

    _Clock(monkeypatch, timedelta(days=1))                                                       # → day 2
    assert (await w["vol"].post(scan_url(w), {"qr_token": season[0]["qr_token"]})).json()["ok"] is True     # new day, new scan
    d2 = (await w["vol"].post(scan_url(w), {"qr_token": day2[0]["qr_token"]})).json()
    assert d2["ok"] and d2["counters"] == {"sold": 2, "scanned_today": 2, "expected_today": 2}
    stats = (await w["owner"].get(f"/societies/{w['s']['id']}/events/{w['ev']['id']}/scan-stats")).json()
    assert [(d["scanned"], d["expected"]) for d in stats["days"]] == [(1, 1), (2, 2), (0, 1)]


async def test_scan_requires_published_event_scope(client):
    w = await live_world(client)
    # an event id from nowhere
    import uuid
    r = await w["vol"].post(f"/societies/{w['s']['id']}/events/{uuid.uuid4()}/scan", {"qr_token": "x" * 20})
    assert r.status_code == 404
    _ = Pass
