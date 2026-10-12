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
