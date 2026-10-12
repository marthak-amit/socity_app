"""A user of society A must never read or write society B's data (events, orders, passes, gallery, members).
This file grows with each milestone; every society-scoped route should appear in the parametrised sweep."""

import pytest_asyncio

from tests.helpers import create_society, join_and_approve, login


@pytest_asyncio.fixture
async def two_societies(client):
    owner_a, owner_b = await login(client, "Owner A"), await login(client, "Owner B")
    sa = await create_society(owner_a, "Society A")
    sb = await create_society(owner_b, "Society B", upi_id="b@okicici")
    member_a = await login(client, "Member A")
    await join_and_approve(owner_a, member_a, sa)
    return dict(owner_a=owner_a, owner_b=owner_b, member_a=member_a, sa=sa, sb=sb)


async def test_outsider_gets_404_for_foreign_society(client, two_societies):
    t = two_societies
    sb = t["sb"]["id"]
    for actor in (t["owner_a"], t["member_a"]):
        assert (await actor.get(f"/societies/{sb}")).status_code == 404
        assert (await actor.get(f"/societies/{sb}/members")).status_code == 404
        assert (await actor.get(f"/societies/{sb}/invite")).status_code == 404
        assert (await actor.patch(f"/societies/{sb}", {"name": "Hacked"})).status_code == 404
        assert (await actor.delete(f"/societies/{sb}", {"confirm_name": "Society B"})).status_code == 404
        assert (await actor.post(f"/societies/{sb}/members/import", {"csv_text": "phone\n+919800000000"})).status_code == 404


async def test_admin_of_a_cannot_touch_members_of_b(client, two_societies):
    t = two_societies
    owner_b_member = (await t["owner_b"].get(f"/societies/{t['sb']['id']}/members")).json()["items"][0]
    base = f"/societies/{t['sb']['id']}/members/{owner_b_member['id']}"
    assert (await t["owner_a"].patch(base, {"role": "member"})).status_code == 404
    assert (await t["owner_a"].delete(base)).status_code == 404


async def test_member_id_from_other_society_is_not_addressable_via_own_society(client, two_societies):
    """Using society A's URL with a membership id that belongs to society B must 404 (no IDOR)."""
    t = two_societies
    b_member = (await t["owner_b"].get(f"/societies/{t['sb']['id']}/members")).json()["items"][0]
    base = f"/societies/{t['sa']['id']}/members/{b_member['id']}"
    assert (await t["owner_a"].patch(base, {"role": "member"})).status_code == 404
    assert (await t["owner_a"].post(base + "/approve")).status_code == 404
    assert (await t["owner_a"].delete(base)).status_code == 404


async def test_multi_society_user_has_independent_roles(client, two_societies):
    t = two_societies
    # owner of A joins B as a plain member: powers don't carry across
    await join_and_approve(t["owner_b"], t["owner_a"], t["sb"])
    assert (await t["owner_a"].get(f"/societies/{t['sb']['id']}")).json()["my_role"] == "member"
    assert (await t["owner_a"].get(f"/societies/{t['sb']['id']}/members")).status_code == 403
    assert (await t["owner_a"].get(f"/societies/{t['sa']['id']}/members")).status_code == 200


async def test_client_supplied_role_is_ignored(client, two_societies):
    t = two_societies
    r = await t["member_a"].post(
        f"/societies/{t['sa']['id']}/members/import", {"csv_text": "phone\n+919800000000"},
        headers={"X-Role": "owner"},
    )
    assert r.status_code == 403


# ------------------------------------------------------------------------------------------------
# Generic sweep: EVERY route containing {society_id} (discovered from the OpenAPI schema, so new routes
# are covered automatically) must hide society A from a non-member and block pending members.
# ------------------------------------------------------------------------------------------------
import uuid  # noqa: E402

from app.main import app  # noqa: E402

PUBLIC_SOCIETY_ROUTES: set[tuple[str, str]] = set()  # none: nothing under /societies/{id} is public


def society_routes():
    schema = app.openapi()
    for path, ops in schema["paths"].items():
        if "{society_id}" not in path:
            continue
        for method in ops:
            if method in ("get", "post", "patch", "put", "delete"):
                yield method.upper(), path


def fill(path: str, society_id: str) -> str:
    import re

    path = path.removeprefix("/api/v1").replace("{society_id}", society_id)
    return re.sub(r"\{[^}]+\}", lambda m: str(uuid.uuid4()), path)


ROUTES = sorted(set(society_routes()))


async def test_sweep_covers_a_meaningful_number_of_routes():
    assert len(ROUTES) >= 40


async def test_every_society_route_404s_for_non_members(client, two_societies):
    t = two_societies
    failures = []
    for method, path in ROUTES:
        url = fill(path, t["sa"]["id"])
        r = await t["owner_b"].client.request(method, f"/api/v1{url}", headers=t["owner_b"].headers, json={})
        # 404 (not 403): a non-member can't even tell the society exists. 422 would mean validation ran before auth.
        if r.status_code != 404:
            failures.append(f"{method} {path} → {r.status_code} {r.text[:100]}")
    assert not failures, "\n".join(failures)


async def test_every_society_route_requires_auth(client, two_societies):
    failures = []
    for method, path in ROUTES:
        r = await client.request(method, f"/api/v1{fill(path, two_societies['sa']['id'])}", json={})
        if r.status_code != 401:
            failures.append(f"{method} {path} → {r.status_code}")
    assert not failures, "\n".join(failures)


async def test_every_society_route_blocks_pending_members(client, two_societies):
    t = two_societies
    pending = await login(client, "Pending")
    await pending.post("/societies/join", {"invite_code": t["sa"]["invite_code"]})
    failures = []
    for method, path in ROUTES:
        r = await pending.client.request(method, f"/api/v1{fill(path, t['sa']['id'])}", headers=pending.headers, json={})
        if r.status_code != 403 or r.json()["detail"]["code"] != "membership_pending":
            failures.append(f"{method} {path} → {r.status_code}")
    assert not failures, "\n".join(failures)


# ------------------------------------------------------------------------------------------------
# Object-level isolation: valid ids from society B addressed through society A's URL, and vice versa.
# ------------------------------------------------------------------------------------------------
from tests.test_orders import order_body, pay, world  # noqa: E402


async def test_events_orders_passes_do_not_leak_across_societies(client):
    owner_a, member_a, _, sa, ev_a, tiers_a = await world(client)
    # society B with its own event, order and approved pass
    owner_b, buyer_b = await login(client, "Owner B"), await login(client, "Buyer B")
    sb = await create_society(owner_b, "Society B", upi_id="b@okicici")
    await join_and_approve(owner_b, buyer_b, sb)
    from tests.test_events import event_body

    ev_b = (await owner_b.post(f"/societies/{sb['id']}/events", event_body())).json()
    await owner_b.post(f"/societies/{sb['id']}/events/{ev_b['id']}/publish")
    ob = (await buyer_b.post(f"/societies/{sb['id']}/events/{ev_b['id']}/orders", order_body(ev_b["tiers"][0]))).json()
    await pay(buyer_b, sb, ob)
    await owner_b.post(f"/societies/{sb['id']}/orders/{ob['id']}/approve")
    pass_b = (await buyer_b.get(f"/societies/{sb['id']}/passes/mine")).json()["items"][0]

    # A's admin addressing B's ids under A's URL → 404
    a = f"/societies/{sa['id']}"
    for r in [
        await owner_a.get(f"{a}/events/{ev_b['id']}"),
        await owner_a.patch(f"{a}/events/{ev_b['id']}", {"title": "pwned"}),
        await owner_a.post(f"{a}/events/{ev_b['id']}/publish"),
        await owner_a.delete(f"{a}/events/{ev_b['id']}"),
        await owner_a.post(f"{a}/events/{ev_b['id']}/tiers", {"name": "x", "price": 0, "capacity": 1}),
        await owner_a.patch(f"{a}/events/{ev_b['id']}/tiers/{ev_b['tiers'][0]['id']}", {"price": 1}),
        await owner_a.get(f"{a}/orders/{ob['id']}"),
        await owner_a.post(f"{a}/orders/{ob['id']}/approve"),
        await owner_a.post(f"{a}/orders/{ob['id']}/reject", {"reason": "nope nope"}),
        await owner_a.post(f"{a}/passes/{pass_b['id']}/revoke"),
        await member_a.post(f"{a}/events/{ev_b['id']}/orders", order_body(ev_b["tiers"][0])),
    ]:
        assert r.status_code == 404, (r.request.method, r.request.url, r.status_code, r.text[:150])
    # A's event, but B's tier id → not found; B's tier cannot be bought through A
    r = await member_a.post(f"{a}/events/{ev_a["id"]}/orders", order_body(ev_b["tiers"][0]))
    assert r.status_code == 404
    # lists are scoped
    assert (await owner_a.get(f"{a}/orders?status=approved")).json()["total"] == 0
    assert all(e["society_id"] == sa["id"] for e in (await owner_a.get(f"{a}/events")).json()["items"])
    assert (await member_a.get("/me/passes")).json()["total"] == 0
    # B is untouched
    assert (await owner_b.get(f"/societies/{sb['id']}/events/{ev_b['id']}")).json()["title"] == "Navratri 2026"
    assert (await buyer_b.get(f"/societies/{sb['id']}/passes/mine")).json()["items"][0]["status"] == "active"


async def test_member_of_both_societies_cannot_mix_resources(client):
    """A user who belongs to A and B must still be scoped per URL: B's order is invisible under A's URL."""
    owner_a, member_a, _, sa, ev_a, tiers_a = await world(client)
    owner_b = await login(client, "Owner B")
    sb = await create_society(owner_b, "Society B", upi_id="b@okicici")
    await join_and_approve(owner_b, member_a, sb)
    from tests.test_events import event_body

    ev_b = (await owner_b.post(f"/societies/{sb['id']}/events", event_body())).json()
    await owner_b.post(f"/societies/{sb['id']}/events/{ev_b['id']}/publish")
    ob = (await member_a.post(f"/societies/{sb['id']}/events/{ev_b['id']}/orders", order_body(ev_b["tiers"][0]))).json()
    assert (await member_a.get(f"/societies/{sa['id']}/orders/{ob['id']}")).status_code == 404
    assert (await member_a.get(f"/societies/{sb['id']}/orders/{ob['id']}")).status_code == 200
    assert (await member_a.get(f"/societies/{sa['id']}/orders/mine")).json()["total"] == 0
