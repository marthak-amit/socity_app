"""Reusable end-to-end fixtures built through the public API."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from tests.helpers import create_society, join_and_approve, login, upload_image
from tests.test_events import event_body, iso


async def buy_and_approve(buyer, admin, s, ev, tier, qty=1, holders=None, utr="100000000001", amount=None):
    r = await buyer.post(f"/societies/{s['id']}/events/{ev['id']}/orders",
                         {"items": [{"tier_id": tier["id"], "qty": qty, "holders": holders or []}]})
    assert r.status_code == 201, r.text
    order = r.json()
    if order["status"] != "approved":
        up = await upload_image(buyer, s["id"], "screenshot")
        r = await buyer.post(f"/societies/{s['id']}/orders/{order['id']}/payment",
                             {"screenshot_upload_id": up, "utr": utr, "paid_amount": amount if amount is not None else order["total_amount"]})
        assert r.status_code == 200, r.text
        r = await admin.post(f"/societies/{s['id']}/orders/{order['id']}/approve")
        assert r.status_code == 200, r.text
    passes = (await buyer.get(f"/societies/{s['id']}/passes/mine?event_id={ev['id']}&limit=100")).json()["items"]
    return order, passes


async def live_world(client, days=1, tiers=None):
    """owner + volunteer + 2 buyers; a published event that is running right now."""
    owner, vol = await login(client, "Owner"), await login(client, "Gate Volunteer")
    buyer, buyer2 = await login(client, "Meera Shah"), await login(client, "Raj Patel")
    s = await create_society(owner)
    await join_and_approve(owner, vol, s)
    await join_and_approve(owner, buyer, s, wing="A", flat="101")
    await join_and_approve(owner, buyer2, s, wing="B", flat="202")
    ist = ZoneInfo("Asia/Kolkata")
    today = datetime.now(ist).replace(hour=0, minute=1, second=0, microsecond=0)  # event runs "all today" in IST
    start, end = today, today.replace(hour=23, minute=58) + timedelta(days=days - 1)
    body = event_body(starts_at=iso(start), ends_at=iso(end),
                      tiers=tiers or [{"name": "Family", "price": 500, "capacity": 50, "per_user_limit": 6},
                                      {"name": "Solo", "price": 200, "capacity": 50, "per_user_limit": 6}])
    ev = (await owner.post(f"/societies/{s['id']}/events", body)).json()
    assert len(ev["days"]) == days, ev["days"]
    assert (await owner.post(f"/societies/{s['id']}/events/{ev['id']}/publish")).status_code == 200
    ev = (await owner.get(f"/societies/{s['id']}/events/{ev['id']}")).json()
    assert (await owner.post(f"/societies/{s['id']}/events/{ev['id']}/volunteers", {"user_id": vol.id})).status_code == 201
    return dict(owner=owner, vol=vol, buyer=buyer, buyer2=buyer2, s=s, ev=ev, tiers={t["name"]: t for t in ev["tiers"]})
