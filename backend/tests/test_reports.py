import io

from openpyxl import load_workbook

from tests.flow import buy_and_approve, live_world
from tests.helpers import upload_image


async def seeded(client):
    w = await live_world(client)
    s, ev, T = w["s"], w["ev"], w["tiers"]
    # buyer (wing A): 2 Family (1000) ; buyer2 (wing B): 1 Family + pending 1 Solo ; vol pays for 1 Solo (wing none)
    _, p1 = await buy_and_approve(w["buyer"], w["owner"], s, ev, T["Family"], 2, utr="200000000001")
    _, p2 = await buy_and_approve(w["buyer2"], w["owner"], s, ev, T["Family"], 1, utr="200000000002")
    r = await w["buyer2"].post(f"/societies/{s['id']}/events/{ev['id']}/orders", {"items": [{"tier_id": T["Solo"]["id"], "qty": 1}]})
    pending = r.json()
    up = await upload_image(w["buyer2"], s["id"], "screenshot")
    await w["buyer2"].post(f"/societies/{s['id']}/orders/{pending['id']}/payment", {"screenshot_upload_id": up, "utr": "200000000003"})
    # one entry scanned
    await w["vol"].post(f"/societies/{s['id']}/events/{ev['id']}/scan", {"qr_token": p1[0]["qr_token"]})
    return w, p1, p2


async def test_report_numbers(client):
    w, _, _ = await seeded(client)
    s, ev = w["s"], w["ev"]
    rep = (await w["owner"].get(f"/societies/{s['id']}/events/{ev['id']}/report")).json()
    t = rep["totals"]
    assert t["collected_amount"] == 1500 and t["pending_count"] == 1 and t["pending_amount"] == 200
    assert t["approved_orders"] == 2 and t["passes_sold"] == 3 and t["passes_scanned"] == 1
    fam = next(x for x in rep["by_tier"] if x["name"] == "Family")
    solo = next(x for x in rep["by_tier"] if x["name"] == "Solo")
    assert (fam["sold"], fam["collected"], fam["scanned"]) == (3, 1500, 1)
    assert (solo["sold"], solo["pending"], solo["collected"]) == (0, 1, 0)
    wings = {x["wing"]: x for x in rep["by_wing"]}
    assert wings["A"]["passes"] == 2 and wings["A"]["collected"] == 1000
    assert wings["B"]["passes"] == 1 and wings["B"]["collected"] == 500
    assert rep["by_day"][0]["scanned"] == 1


async def test_reports_are_admin_only(client):
    w, _, _ = await seeded(client)
    base = f"/societies/{w['s']['id']}/events/{w['ev']['id']}/report"
    for actor in (w["buyer"], w["vol"]):
        assert (await actor.get(base)).status_code == 403
        assert (await actor.get(base + "/export?format=csv")).status_code == 403


async def test_export_csv_and_xlsx(client):
    w, _, _ = await seeded(client)
    base = f"/societies/{w['s']['id']}/events/{w['ev']['id']}/report/export"
    r = await w["owner"].get(base + "?format=csv")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"] and r.headers["content-disposition"].endswith('.csv"')
    text = r.content.decode("utf-8-sig")
    lines = text.strip().splitlines()
    assert lines[0].startswith("Order ref,Status") and len(lines) == 4
    assert "200000000003" in text and "Meera Shah" in text

    r = await w["owner"].get(base + "?format=xlsx")
    assert r.status_code == 200 and "spreadsheetml" in r.headers["content-type"]
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Summary", "By tier", "By wing", "By day", "Orders"]
    summary = {row[0]: row[1] for row in wb["Summary"].iter_rows(min_row=2, values_only=True)}
    assert summary["Collected (₹)"] == 1500 and summary["Passes sold"] == 3
    assert wb["Orders"].max_row == 4
    assert [c.value for c in wb["By tier"][2]][:1] == ["Solo"]


async def test_export_neutralises_formula_injection(client):
    w, _, _ = await seeded(client)
    await w["buyer"].patch("/me", {"name": "=HYPERLINK(\"http://evil\",\"x\")"})
    base = f"/societies/{w['s']['id']}/events/{w['ev']['id']}/report/export"
    text = (await w["owner"].get(base + "?format=csv")).content.decode("utf-8-sig")
    assert "'=HYPERLINK" in text and ",=HYPERLINK" not in text
    wb = load_workbook(io.BytesIO((await w["owner"].get(base + "?format=xlsx")).content))
    names = [row[3] for row in wb["Orders"].iter_rows(min_row=2, values_only=True)]
    assert all(not (n or "").startswith("=") for n in names)


async def test_export_is_audited(client):
    from sqlalchemy import select

    from app.core.db import SessionLocal
    from app.models import AuditLog

    w, _, _ = await seeded(client)
    await w["owner"].get(f"/societies/{w['s']['id']}/events/{w['ev']['id']}/report/export?format=csv")
    async with SessionLocal() as db:
        assert (await db.scalars(select(AuditLog.action).where(AuditLog.action == "report.export"))).all()
