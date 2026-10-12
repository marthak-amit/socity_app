from app.core.phone import normalize_phone
from tests.helpers import create_society, join_and_approve, login


async def test_create_society_makes_owner_with_invite_code(client):
    owner = await login(client, "Owner")
    s = await create_society(owner)
    assert s["my_role"] == "owner" and len(s["invite_code"]) == 8
    assert "min_two_admins" in s["warnings"]
    me = (await owner.get("/me")).json()
    assert me["memberships"][0]["role"] == "owner" and me["memberships"][0]["society"]["id"] == s["id"]
    inv = (await owner.get(f"/societies/{s['id']}/invite")).json()
    assert inv["deep_link"] == f"societypass://join?code={s['invite_code']}" and s["invite_code"] in inv["web_link"]


async def test_invalid_upi_rejected(client):
    owner = await login(client)
    r = await owner.post("/societies", {"name": "X Society", "city": "Surat", "upi_id": "not-a-upi"})
    assert r.status_code == 422


async def test_join_pending_then_approve_flow(client):
    owner, member = await login(client, "Owner"), await login(client, "Meera")
    s = await create_society(owner)
    r = await member.post("/societies/lookup", {"invite_code": s["invite_code"].lower()})
    assert r.status_code == 200 and r.json()["name"] == "Green Valley"
    r = await member.post("/societies/join", {"invite_code": s["invite_code"], "wing": "B", "flat_no": "204"})
    assert r.status_code == 201 and r.json()["status"] == "pending"
    mid = r.json()["id"]
    # pending members can't see society data
    assert (await member.get(f"/societies/{s['id']}")).status_code == 403
    # ...and they can't see admin queues
    assert (await member.get(f"/societies/{s['id']}/members")).status_code == 403
    pending = (await owner.get(f"/societies/{s['id']}/members?status=pending")).json()
    assert pending["total"] == 1 and pending["items"][0]["flat_no"] == "204"
    assert (await owner.post(f"/societies/{s['id']}/members/{mid}/approve")).status_code == 200
    assert (await member.get(f"/societies/{s['id']}")).status_code == 200
    # a member does not see the invite code
    assert (await member.get(f"/societies/{s['id']}")).json()["invite_code"] is None
    assert (await member.get(f"/societies/{s['id']}/invite")).status_code == 403


async def test_join_with_bad_code_and_duplicate_join(client):
    owner, member = await login(client), await login(client)
    s = await create_society(owner)
    assert (await member.post("/societies/join", {"invite_code": "ZZZZZZZZ"})).status_code == 404
    await join_and_approve(owner, member, s)
    assert (await member.post("/societies/join", {"invite_code": s["invite_code"]})).status_code == 409


async def test_reject_join_then_rejoin(client):
    owner, member = await login(client), await login(client)
    s = await create_society(owner)
    mid = (await member.post("/societies/join", {"invite_code": s["invite_code"]})).json()["id"]
    assert (await owner.post(f"/societies/{s['id']}/members/{mid}/reject")).status_code == 200
    assert (await member.get("/me")).json()["memberships"] == []
    r = await member.post("/societies/join", {"invite_code": s["invite_code"]})
    assert r.status_code == 201 and r.json()["status"] == "pending"


async def test_join_notifies_admins_and_approval_notifies_member(client):
    from app.services.push import push

    owner, member = await login(client), await login(client, "Meera")
    s = await create_society(owner)
    await member.post("/societies/join", {"invite_code": s["invite_code"]})
    assert any(m.title == "New join request" and m.user_ids == [__import__("uuid").UUID(owner.id)] for m in push.outbox)
    mid = (await owner.get(f"/societies/{s['id']}/members?status=pending")).json()["items"][0]["id"]
    await owner.post(f"/societies/{s['id']}/members/{mid}/approve")
    assert any(m.data.get("type") == "join_approved" for m in push.outbox)


async def test_csv_import_auto_approves_and_activates_pending(client):
    owner, known, waiting = await login(client, "Owner"), await login(client, "Known"), await login(client, "Waiting")
    s = await create_society(owner)
    await waiting.post("/societies/join", {"invite_code": s["invite_code"]})  # already pending
    csv_text = f"phone,name,wing,flat_no\n{known.phone},Known Person,C,303\n{waiting.phone},Waiting,D,404\nbadnumber,x,y,z\n"
    r = await owner.post(f"/societies/{s['id']}/members/import", {"csv_text": csv_text})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["created"] == 2 and out["activated"] == 1 and len(out["errors"]) == 1
    # the known number is auto-approved on join, flat taken from CSV
    r = await known.post("/societies/join", {"invite_code": s["invite_code"]})
    assert r.json()["status"] == "active" and r.json()["flat_no"] == "303" and r.json()["wing"] == "C"
    members = (await owner.get(f"/societies/{s['id']}/members?status=active")).json()
    assert members["total"] == 3


async def test_csv_import_requires_phone_header(client):
    owner = await login(client)
    s = await create_society(owner)
    r = await owner.post(f"/societies/{s['id']}/members/import", {"csv_text": "name,flat\nA,1\n"})
    assert r.status_code == 400


async def test_role_management_rules(client):
    owner, admin, vol, member = [await login(client, n) for n in ("Owner", "Admin", "Vol", "Mem")]
    s = await create_society(owner)
    admin_mid = await join_and_approve(owner, admin, s, role="admin")
    vol_mid = await join_and_approve(owner, vol, s, role="volunteer")
    mem_mid = await join_and_approve(admin, member, s)
    base = f"/societies/{s['id']}/members"
    owner_mid = (await owner.get(base + "?role=owner")).json()["items"][0]["id"]

    # admin may toggle volunteer/member but can't create admins or touch the owner/other admins
    assert (await admin.patch(f"{base}/{mem_mid}", {"role": "volunteer"})).status_code == 200
    assert (await admin.patch(f"{base}/{mem_mid}", {"role": "admin"})).status_code == 403
    assert (await admin.patch(f"{base}/{owner_mid}", {"role": "member"})).status_code == 403
    assert (await admin.delete(f"{base}/{owner_mid}")).status_code == 403
    # nobody changes their own role; nobody can be made owner
    assert (await owner.patch(f"{base}/{owner_mid}", {"role": "admin"})).status_code == 403
    assert (await owner.patch(f"{base}/{admin_mid}", {"role": "owner"})).status_code == 403
    # owner can promote/demote admins
    r = await owner.patch(f"{base}/{vol_mid}", {"role": "admin"})
    assert r.status_code == 200 and r.json()["member"]["role"] == "admin"
    # volunteers/members have no access to member management at all
    assert (await member.get(base)).status_code == 403
    assert (await member.patch(f"{base}/{vol_mid}", {"role": "member"})).status_code == 403


async def test_min_two_admins_warning_follows_role_changes(client):
    owner, other = await login(client), await login(client)
    s = await create_society(owner)
    mid = await join_and_approve(owner, other, s)
    r = await owner.patch(f"/societies/{s['id']}/members/{mid}", {"role": "admin"})
    assert "min_two_admins" not in r.json()["warnings"]
    r = await owner.patch(f"/societies/{s['id']}/members/{mid}", {"role": "member"})
    assert "min_two_admins" in r.json()["warnings"]
    assert "min_two_admins" in (await owner.get(f"/societies/{s['id']}")).json()["warnings"]


async def test_remove_member_and_leave(client):
    owner, m1, m2 = await login(client), await login(client), await login(client)
    s = await create_society(owner)
    mid1 = await join_and_approve(owner, m1, s)
    await join_and_approve(owner, m2, s)
    assert (await owner.delete(f"/societies/{s['id']}/members/{mid1}")).status_code == 200
    assert (await m1.get(f"/societies/{s['id']}")).status_code == 403
    assert (await m2.post(f"/societies/{s['id']}/leave")).status_code == 200
    assert (await owner.post(f"/societies/{s['id']}/leave")).status_code == 403


async def test_update_society_admin_only_and_audited(client):
    owner, member = await login(client), await login(client)
    s = await create_society(owner)
    await join_and_approve(owner, member, s)
    assert (await member.patch(f"/societies/{s['id']}", {"upi_id": "evil@upi"})).status_code == 403
    r = await owner.patch(f"/societies/{s['id']}", {"upi_id": "new@okaxis", "name": "Green Valley II"})
    assert r.status_code == 200 and r.json()["upi_id"] == "new@okaxis"
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models import AuditLog

    async with SessionLocal() as db:
        logs = (await db.scalars(select(AuditLog).where(AuditLog.action == "society.update"))).all()
    assert logs and logs[0].meta["changes"]["upi_id"] == {"from": "greenvalley@okhdfc", "to": "new@okaxis"}


async def test_rotate_invite_invalidates_old_code(client):
    owner, member = await login(client), await login(client)
    s = await create_society(owner)
    new = (await owner.post(f"/societies/{s['id']}/invite/rotate")).json()["code"]
    assert new != s["invite_code"]
    assert (await member.post("/societies/join", {"invite_code": s["invite_code"]})).status_code == 404
    assert (await member.post("/societies/join", {"invite_code": new})).status_code == 201


async def test_delete_society_owner_only_with_confirmation(client):
    owner, admin = await login(client), await login(client)
    s = await create_society(owner)
    await join_and_approve(owner, admin, s, role="admin")
    assert (await admin.delete(f"/societies/{s['id']}", {"confirm_name": s["name"]})).status_code == 403
    assert (await owner.delete(f"/societies/{s['id']}", {"confirm_name": "wrong"})).status_code == 400
    assert (await owner.delete(f"/societies/{s['id']}", {"confirm_name": s["name"]})).status_code == 200
    assert (await owner.get(f"/societies/{s['id']}")).status_code == 404
    assert (await owner.get("/me")).json()["memberships"] == []


async def test_members_list_pagination_and_search(client):
    owner = await login(client)
    s = await create_society(owner)
    for i in range(5):
        m = await login(client, f"Resident {i}")
        await join_and_approve(owner, m, s, flat=f"10{i}")
    page = (await owner.get(f"/societies/{s['id']}/members?limit=2&offset=0")).json()
    assert len(page["items"]) == 2 and page["total"] == 6
    found = (await owner.get(f"/societies/{s['id']}/members?q=Resident 3")).json()
    assert found["total"] == 1
    assert (await owner.get(f"/societies/{s['id']}/members?limit=1000")).status_code == 422


async def test_phone_normalised_in_csv(client):
    assert normalize_phone("98765 43210") == "+919876543210"
