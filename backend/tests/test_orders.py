import asyncio
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select, update

from app.core.db import SessionLocal
from app.core.security import verify_qr_token
from app.models import Order
from app.services.orders import expire_pending_orders
from app.services.push import push
from tests.helpers import create_society, join_and_approve, login, upload_image
from tests.test_events import event_body, iso


class World:
    """owner + admin + 2 members in one society with a published paid event (tiers: Family 500 cap 5, Kids 0 cap 10)."""


async def world(client, capacity=5, per_user=4):
    owner, member, member2 = await login(client, "Owner"), await login(client, "Meera Shah"), await login(client, "Raj Patel")
    s = await create_society(owner)
    await join_and_approve(owner, member, s, wing="A", flat="101")
    await join_and_approve(owner, member2, s, wing="B", flat="202")
    body = event_body(tiers=[
        {"name": "Family", "price": 500, "capacity": capacity, "per_user_limit": per_user},
        {"name": "Solo", "price": 200, "capacity": 10, "per_user_limit": 2, "allow_guests": False},
    ])
    ev = (await owner.post(f"/societies/{s['id']}/events", body)).json()
    assert (await owner.post(f"/societies/{s['id']}/events/{ev['id']}/publish")).status_code == 200
    ev = (await owner.get(f"/societies/{s['id']}/events/{ev['id']}")).json()
    tiers = {t["name"]: t for t in ev["tiers"]}
    return owner, member, member2, s, ev, tiers


def order_body(tier, qty=1, holders=None):
    return {"items": [{"tier_id": tier["id"], "qty": qty, "holders": holders or []}]}


async def place(actor, s, ev, tier, qty=1, holders=None):
    return await actor.post(f"/societies/{s['id']}/events/{ev['id']}/orders", order_body(tier, qty, holders))


async def pay(actor, s, order, utr="123456789012", amount=None, shot=True):
    up = await upload_image(actor, s["id"], "screenshot") if shot else None
    return await actor.post(f"/societies/{s['id']}/orders/{order['id']}/payment",
                            {"screenshot_upload_id": up, "utr": utr, "paid_amount": amount if amount is not None else order["total_amount"]})


async def test_full_happy_path_order_to_signed_qr(client):
    owner, member, _, s, ev, tiers = await world(client)
    r = await place(member, s, ev, tiers["Family"], 2, [{"name": "Meera", "type": "member"}, {"name": "Guest Anil", "type": "guest"}])
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["status"] == "pending" and order["total_amount"] == 1000 and order["ref_code"].startswith("SP-")
    # UPI intent link per the spec: pa, pn, am, tn=<order ref>
    q = parse_qs(urlparse(order["payment"]["upi_uri"]).query)
    assert order["payment"]["upi_uri"].startswith("upi://pay?")
    assert q["pa"] == ["greenvalley@okhdfc"] and q["am"] == ["1000.00"] and q["tn"] == [f"Order {order['ref_code']}"] and q["cu"] == ["INR"]
    # capacity is reserved while pending
    ev2 = (await member.get(f"/societies/{s['id']}/events/{ev['id']}")).json()
    fam = next(t for t in ev2["tiers"] if t["name"] == "Family")
    assert fam["pending"] == 2 and fam["remaining"] == 3 and fam["sold"] == 0
    # before payment proof it is not in the admin review queue, and cannot be approved
    assert (await owner.get(f"/societies/{s['id']}/orders")).json()["total"] == 0
    assert (await owner.post(f"/societies/{s['id']}/orders/{order['id']}/approve")).status_code == 409
    r = await pay(member, s, order, utr="402611223344")
    assert r.status_code == 200 and r.json()["payment_submitted_at"] and r.json()["flags"] == []  # members don't see flags
    queue = (await owner.get(f"/societies/{s['id']}/orders")).json()
    assert queue["total"] == 1
    item = queue["items"][0]
    assert item["utr"] == "402611223344" and item["member"]["name"] == "Meera Shah" and item["member"]["flat_no"] == "101"
    assert item["screenshot_url"] and item["flags"] == []
    shot = await client.get(item["screenshot_url"])
    assert shot.status_code == 200 and shot.headers["content-type"] == "image/jpeg"
    # approve → passes + signed QR + push
    r = await owner.post(f"/societies/{s['id']}/orders/{order['id']}/approve")
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert any(m.data.get("type") == "order_approved" for m in push.outbox)
    passes = (await member.get(f"/societies/{s['id']}/passes/mine")).json()
    assert passes["total"] == 2
    names = {p["holder_name"]: p for p in passes["items"]}
    assert set(names) == {"Meera", "Guest Anil"} and names["Guest Anil"]["holder_type"] == "guest"
    for p in passes["items"]:
        tok = verify_qr_token(p["qr_token"])
        assert str(tok["pass_id"]) == p["id"] and str(tok["event_id"]) == ev["id"]
        assert p["tier_name"] == "Family" and p["event"]["title"] == "Navratri 2026" and p["valid_days"] == "all"
    # cross-society "my passes" endpoint shows the same
    assert (await member.get("/me/passes")).json()["total"] == 2
    ev3 = (await member.get(f"/societies/{s['id']}/events/{ev['id']}")).json()
    assert next(t for t in ev3["tiers"] if t["name"] == "Family")["sold"] == 2
    # approving twice is rejected
    assert (await owner.post(f"/societies/{s['id']}/orders/{order['id']}/approve")).status_code == 409


async def test_default_holders_when_not_supplied(client):
    owner, member, _, s, ev, tiers = await world(client)
    order = (await place(member, s, ev, tiers["Family"], 2)).json()
    await pay(member, s, order)
    await owner.post(f"/societies/{s['id']}/orders/{order['id']}/approve")
    names = sorted(p["holder_name"] for p in (await member.get(f"/societies/{s['id']}/passes/mine")).json()["items"])
    assert names == ["Meera Shah", "Meera Shah +1"]


async def test_holder_validation(client):
    _, member, _, s, ev, tiers = await world(client)
    assert (await place(member, s, ev, tiers["Family"], 2, [{"name": "Only one"}])).status_code == 400
    r = await place(member, s, ev, tiers["Solo"], 1, [{"name": "Visitor", "type": "guest"}])
    assert r.status_code == 400 and r.json()["detail"]["code"] == "guests_not_allowed"
    r = await place(member, s, ev, tiers["Family"], 1, [{"name": "  ", "type": "member"}])
    assert r.status_code == 400 and r.json()["detail"]["code"] == "holder_name_required"


async def test_capacity_and_per_user_limit(client):
    owner, member, member2, s, ev, tiers = await world(client, capacity=5, per_user=3)
    assert (await place(member, s, ev, tiers["Family"], 4)).status_code == 409   # per-user limit 3
    assert (await place(member, s, ev, tiers["Family"], 3)).status_code == 201
    r = await place(member, s, ev, tiers["Family"], 1)                           # 3 held + 1 > 3
    assert r.status_code == 409 and r.json()["detail"]["code"] == "per_user_limit_exceeded"
    r = await place(member2, s, ev, tiers["Family"], 3)                          # only 2 left
    assert r.status_code == 409 and r.json()["detail"]["code"] == "insufficient_capacity" and r.json()["detail"]["remaining"] == 2
    assert (await place(member2, s, ev, tiers["Family"], 2)).status_code == 201
    r = await place(owner, s, ev, tiers["Family"], 1)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "sold_out"


async def test_reject_and_cancel_release_capacity(client):
    owner, member, member2, s, ev, tiers = await world(client, capacity=2, per_user=2)
    o1 = (await place(member, s, ev, tiers["Family"], 2)).json()
    assert (await place(member2, s, ev, tiers["Family"], 1)).status_code == 409
    await pay(member, s, o1)
    r = await owner.post(f"/societies/{s['id']}/orders/{o1['id']}/reject", {"reason": "UTR not found in bank statement"})
    assert r.status_code == 200 and r.json()["status"] == "rejected" and r.json()["reject_reason"].startswith("UTR")
    assert any(m.data.get("type") == "order_rejected" for m in push.outbox)
    o2 = (await place(member2, s, ev, tiers["Family"], 2)).json()                 # seats are free again
    assert (await member2.post(f"/societies/{s['id']}/orders/{o2['id']}/cancel")).status_code == 200
    assert (await place(member, s, ev, tiers["Family"], 2)).status_code == 201
    assert (await owner.post(f"/societies/{s['id']}/orders/{o1['id']}/reject", {"reason": "again please"})).status_code == 409
    assert (await owner.post(f"/societies/{s['id']}/orders/{o1['id']}/reject", {"reason": "x"})).status_code == 422


async def test_unpaid_orders_expire_after_ttl_but_submitted_ones_do_not(client):
    owner, member, member2, s, ev, tiers = await world(client, capacity=2, per_user=2)
    unpaid = (await place(member, s, ev, tiers["Family"], 1)).json()
    paid = (await place(member2, s, ev, tiers["Family"], 1)).json()
    await pay(member2, s, paid)
    async with SessionLocal() as db:   # age both orders by 3 days
        await db.execute(update(Order).values(created_at=datetime.now(UTC) - timedelta(days=3)))
        await db.commit()
    # lazy expiry: the unpaid hold no longer counts even before the job runs
    ev2 = (await owner.get(f"/societies/{s['id']}/events/{ev['id']}")).json()
    assert next(t for t in ev2["tiers"] if t["name"] == "Family")["remaining"] == 1
    assert (await pay(member, s, unpaid)).status_code == 409                       # can't pay an expired order
    assert await expire_pending_orders() == 1
    got = (await member.get(f"/societies/{s['id']}/orders/{unpaid['id']}")).json()
    assert got["status"] == "cancelled" and got["reject_reason"] == "expired"
    assert (await owner.get(f"/societies/{s['id']}/orders/{paid['id']}")).json()["status"] == "pending"
    assert await expire_pending_orders() == 0


async def test_flags_duplicate_utr_across_societies_amount_mismatch_missing_utr(client):
    owner, member, member2, s, ev, tiers = await world(client)
    o1 = (await place(member, s, ev, tiers["Family"], 1)).json()
    o2 = (await place(member2, s, ev, tiers["Family"], 1)).json()
    await pay(member, s, o1, utr="111111111111")
    # same UTR, different member, plus a screenshot-only/amount-mismatch variant
    await pay(member2, s, o2, utr="111111111111", amount=400)
    q = {o["id"]: o for o in (await owner.get(f"/societies/{s['id']}/orders")).json()["items"]}
    assert set(q[o2["id"]]["flags"]) == {"duplicate_utr", "amount_mismatch"}
    assert q[o1["id"]]["flags"] == ["duplicate_utr"]          # the earlier order is flagged too
    # missing UTR (screenshot only)
    o3 = (await place(member, s, ev, tiers["Solo"], 1)).json()
    up = await upload_image(member, s["id"], "screenshot")
    await member.post(f"/societies/{s['id']}/orders/{o3['id']}/payment", {"screenshot_upload_id": up})
    got = (await owner.get(f"/societies/{s['id']}/orders/{o3['id']}")).json()
    assert got["flags"] == ["missing_utr"]
    # a different society reusing the UTR is caught platform-wide
    owner_b, buyer_b = await login(client, "Owner B"), await login(client, "Buyer B")
    sb = await create_society(owner_b, "Society B", upi_id="b@okicici")
    await join_and_approve(owner_b, buyer_b, sb)
    evb = (await owner_b.post(f"/societies/{sb['id']}/events", event_body())).json()
    await owner_b.post(f"/societies/{sb['id']}/events/{evb['id']}/publish")
    ob = (await place(buyer_b, sb, evb, evb["tiers"][0], 1)).json()
    await pay(buyer_b, sb, ob, utr="111111111111")
    assert (await owner_b.get(f"/societies/{sb['id']}/orders/{ob['id']}")).json()["flags"] == ["duplicate_utr"]
    # filters
    flagged = (await owner.get(f"/societies/{s['id']}/orders?flagged=true")).json()
    assert flagged["total"] == 3
    clean = (await owner.get(f"/societies/{s['id']}/orders?flagged=false")).json()
    assert clean["total"] == 0
    summary = (await owner.get(f"/societies/{s['id']}/orders/summary")).json()
    assert summary["pending"] == 3 and summary["pending_flagged"] == 3


async def test_bulk_approve_skips_flagged_unless_forced(client):
    owner, member, member2, s, ev, tiers = await world(client)
    good = (await place(member, s, ev, tiers["Family"], 1)).json()
    bad = (await place(member2, s, ev, tiers["Family"], 1)).json()
    unpaid = (await place(member, s, ev, tiers["Solo"], 1)).json()
    await pay(member, s, good, utr="222222222222")
    await pay(member2, s, bad, utr="333333333333", amount=1)
    ids = [good["id"], bad["id"], unpaid["id"]]
    r = (await owner.post(f"/societies/{s['id']}/orders/bulk-approve", {"order_ids": ids})).json()
    assert r["approved"] == [good["id"]]
    reasons = {x["id"]: x["reason"] for x in r["skipped"]}
    assert reasons == {bad["id"]: "flagged", unpaid["id"]: "payment_not_submitted"}
    r = (await owner.post(f"/societies/{s['id']}/orders/bulk-approve", {"order_ids": [bad["id"]], "include_flagged": True})).json()
    assert r["approved"] == [bad["id"]]
    assert (await member2.get(f"/societies/{s['id']}/passes/mine")).json()["total"] == 1


async def test_free_event_auto_approves_and_issues_passes(client):
    owner, member = await login(client, "Owner"), await login(client, "Meera")
    s = await create_society(owner, upi_id=None)
    await join_and_approve(owner, member, s)
    body = event_body(is_paid=False, tiers=[{"name": "Entry", "price": 0, "capacity": 20, "per_user_limit": 4}])
    ev = (await owner.post(f"/societies/{s['id']}/events", body)).json()
    assert (await owner.post(f"/societies/{s['id']}/events/{ev['id']}/publish")).status_code == 200
    r = await place(member, s, ev, ev["tiers"][0], 2)
    assert r.status_code == 201 and r.json()["status"] == "approved" and r.json()["payment"] is None
    assert (await member.get(f"/societies/{s['id']}/passes/mine")).json()["total"] == 2


async def test_booking_closed_rules(client):
    owner, member, _, s, ev, tiers = await world(client)
    await owner.post(f"/societies/{s['id']}/events/{ev['id']}/close")
    r = await place(member, s, ev, tiers["Family"])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "booking_closed"
    await owner.post(f"/societies/{s['id']}/events/{ev['id']}/reopen")
    await owner.patch(f"/societies/{s['id']}/events/{ev['id']}", {"booking_deadline": iso(datetime.now(UTC) + timedelta(seconds=1))})
    await asyncio.sleep(1.2)
    assert (await place(member, s, ev, tiers["Family"])).json()["detail"]["code"] == "booking_closed"


async def test_payment_proof_validation(client):
    _, member, _, s, ev, tiers = await world(client)
    o = (await place(member, s, ev, tiers["Family"])).json()
    base = f"/societies/{s['id']}/orders/{o['id']}/payment"
    assert (await member.post(base, {})).status_code == 400
    assert (await member.post(base, {"utr": "12345"})).status_code == 422
    assert (await member.post(base, {"utr": "ABCDEFGHIJKL"})).status_code == 422
    assert (await member.post(base, {"utr": "1234 5678 9012"})).json()["utr"] == "123456789012"
    # resubmitting replaces the proof while still pending
    assert (await pay(member, s, o, utr="999999999999")).json()["utr"] == "999999999999"


async def test_orders_are_private_to_buyer_and_admins(client):
    owner, member, member2, s, ev, tiers = await world(client)
    o = (await place(member, s, ev, tiers["Family"])).json()
    await pay(member, s, o)
    base = f"/societies/{s['id']}/orders/{o['id']}"
    assert (await member2.get(base)).status_code == 404                           # other member
    assert (await member2.post(base + "/cancel")).status_code == 404
    assert (await member2.post(base + "/payment", {"utr": "123456789012"})).status_code == 404
    assert (await member2.post(base + "/approve")).status_code == 403
    assert (await member2.get(f"/societies/{s['id']}/orders")).status_code == 403
    mine = (await member.get(base)).json()
    assert mine["screenshot_url"] is None and mine["has_screenshot"] is True and mine["member"] is None
    assert (await owner.get(base)).json()["screenshot_url"]


async def test_concurrent_orders_cannot_oversell_last_seat(client):
    owner, member, member2, s, ev, tiers = await world(client, capacity=1, per_user=1)
    r1, r2 = await asyncio.gather(place(member, s, ev, tiers["Family"]), place(member2, s, ev, tiers["Family"]))
    assert sorted([r1.status_code, r2.status_code]) == [201, 409]


async def test_event_cancel_cancels_pending_orders(client):
    owner, member, _, s, ev, tiers = await world(client)
    o = (await place(member, s, ev, tiers["Family"])).json()
    await owner.post(f"/societies/{s['id']}/events/{ev['id']}/cancel")
    got = (await member.get(f"/societies/{s['id']}/orders/{o['id']}")).json()
    assert got["status"] == "cancelled" and got["reject_reason"] == "event_cancelled"


async def test_admin_actions_are_audited(client):
    from app.models import AuditLog

    owner, member, _, s, ev, tiers = await world(client)
    o = (await place(member, s, ev, tiers["Family"])).json()
    await pay(member, s, o)
    await owner.post(f"/societies/{s['id']}/orders/{o['id']}/approve")
    async with SessionLocal() as db:
        logs = (await db.scalars(select(AuditLog).where(AuditLog.entity == "order"))).all()
    assert [log.action for log in logs] == ["order.approve"] and logs[0].actor_id.hex == owner.id.replace("-", "")
    assert logs[0].meta["amount"] == 500


async def test_revoke_pass(client):
    owner, member, _, s, ev, tiers = await world(client)
    o = (await place(member, s, ev, tiers["Family"])).json()
    await pay(member, s, o)
    await owner.post(f"/societies/{s['id']}/orders/{o['id']}/approve")
    p = (await member.get(f"/societies/{s['id']}/passes/mine")).json()["items"][0]
    assert (await member.post(f"/societies/{s['id']}/passes/{p['id']}/revoke")).status_code == 403
    assert (await owner.post(f"/societies/{s['id']}/passes/{p['id']}/revoke")).status_code == 200
    assert (await member.get(f"/societies/{s['id']}/passes/mine")).json()["items"][0]["status"] == "revoked"
