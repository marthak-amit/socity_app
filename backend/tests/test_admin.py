from sqlalchemy import update

from app.core.db import SessionLocal
from app.models import User
from tests.flow import buy_and_approve, live_world
from tests.helpers import create_society, join_and_approve, login, upload_image


async def make_super(client):
    a = await login(client, "Platform")
    async with SessionLocal() as db:
        await db.execute(update(User).where(User.phone == a.user["phone"]).values(is_super_admin=True))
        await db.commit()
    return a


async def test_only_super_admin_can_use_admin_api(client):
    owner = await login(client, "Owner")
    await create_society(owner)
    for path in ("/admin/stats", "/admin/societies", "/admin/orders/flagged", "/admin/audit-logs"):
        assert (await owner.get(path)).status_code == 403
    assert (await client.get("/api/v1/admin/stats")).status_code == 401
    sup = await make_super(client)
    assert (await sup.get("/admin/stats")).status_code == 200


async def test_super_admin_is_not_a_society_member(client):
    """Platform admins get no implicit access to society data (scoping still applies)."""
    sup = await make_super(client)
    owner = await login(client, "Owner")
    s = await create_society(owner)
    assert (await sup.get(f"/societies/{s['id']}")).status_code == 404
    assert (await sup.get(f"/societies/{s['id']}/orders")).status_code == 404


async def test_super_admin_phone_env_bootstrap(client, monkeypatch):
    from app.api.v1 import auth as auth_module
    monkeypatch.setattr(auth_module.settings, "super_admin_phones", "+919876500000")
    a = await login(client, "Boss", phone="+919876500000")
    assert a.user["is_super_admin"] is True and (await a.get("/admin/ping")).status_code == 200


async def test_stats_societies_and_suspension_flow(client):
    sup = await make_super(client)
    w = await live_world(client)
    await buy_and_approve(w["buyer"], w["owner"], w["s"], w["ev"], w["tiers"]["Family"], 2)
    st = (await sup.get("/admin/stats")).json()
    assert st["societies"] == {"active": 1} and st["orders"] == {"approved": 1} and st["collected_amount"] == 1000 and st["passes"] == 2
    page = (await sup.get("/admin/societies?q=green")).json()
    row = page["items"][0]
    assert page["total"] == 1 and row["members"] == 4 and row["collected_amount"] == 1000 and row["owner_name"] == "Owner"

    r = await sup.post(f"/admin/societies/{w['s']['id']}/suspend", {"reason": "Fraud complaint #12"})
    assert r.status_code == 200 and r.json()["status"] == "suspended"
    # suspended: members and admins are locked out of society data, but can still see the status
    assert (await w["buyer"].get(f"/societies/{w['s']['id']}/events")).json()["detail"]["code"] == "society_suspended"
    assert (await w["owner"].get(f"/societies/{w['s']['id']}/orders")).status_code == 403
    assert (await w["vol"].post(f"/societies/{w['s']['id']}/events/{w['ev']['id']}/scan", {"qr_token": "x"})).status_code == 403
    assert (await w["buyer"].get(f"/societies/{w['s']['id']}")).json()["status"] == "suspended"
    # ...and nobody can join it
    newbie = await login(client, "Newbie")
    r = await newbie.post("/societies/join", {"invite_code": w["s"]["invite_code"]})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "society_suspended"
    assert (await sup.post(f"/admin/societies/{w['s']['id']}/suspend", {"reason": "again please"})).status_code == 409
    assert (await sup.get("/admin/societies?status=suspended")).json()["total"] == 1

    assert (await sup.post(f"/admin/societies/{w['s']['id']}/unsuspend")).json()["status"] == "active"
    assert (await w["buyer"].get(f"/societies/{w['s']['id']}/events")).status_code == 200
    actions = [a["action"] for a in (await sup.get(f"/admin/audit-logs?society_id={w['s']['id']}")).json()["items"]]
    assert "society.suspend" in actions and "society.unsuspend" in actions and "order.approve" in actions


async def test_flagged_orders_view_hides_screenshots(client):
    sup = await make_super(client)
    w = await live_world(client)
    ev, s = w["ev"], w["s"]
    for buyer, utr in ((w["buyer"], "300000000001"), (w["buyer2"], "300000000001")):
        r = await buyer.post(f"/societies/{s['id']}/events/{ev['id']}/orders", {"items": [{"tier_id": w["tiers"]["Solo"]["id"], "qty": 1}]})
        up = await upload_image(buyer, s["id"], "screenshot")
        await buyer.post(f"/societies/{s['id']}/orders/{r.json()['id']}/payment", {"screenshot_upload_id": up, "utr": utr})
    flagged = (await sup.get("/admin/orders/flagged")).json()
    assert flagged["total"] == 2 and all(o["flags"] == ["duplicate_utr"] for o in flagged["items"])
    assert all("screenshot" not in k for o in flagged["items"] for k in o)
    assert {o["society_name"] for o in flagged["items"]} == {"Green Valley"}
    _ = join_and_approve


async def test_audit_log_filters(client):
    sup = await make_super(client)
    w = await live_world(client)
    await buy_and_approve(w["buyer"], w["owner"], w["s"], w["ev"], w["tiers"]["Solo"], 1)
    logs = (await sup.get("/admin/audit-logs?action=order.")).json()
    assert logs["total"] == 1 and logs["items"][0]["actor_name"] == "Owner" and logs["items"][0]["society_name"] == "Green Valley"
    assert (await sup.get(f"/admin/audit-logs?actor_id={w['owner'].id}&limit=2")).json()["total"] >= 3
