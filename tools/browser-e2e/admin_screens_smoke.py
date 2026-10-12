import asyncio
import runpy, os
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "purchase_flow.py")).read().split("async def main")[0])
BAD = ("FlutterError", "Uncaught", "Exception", "RenderFlex", "overflowed")

async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=["--no-sandbox", "--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"])
        m = await login(b, "9800000011")            # Ramesh — owner
        await m.get_by_role("tab", name="Manage").wait_for(state="attached", timeout=30000)
        results = {}
        async def visit(name, opener, wait_text, shot):
            LOG.clear()
            await opener()
            await m.wait_for_timeout(2500)
            body = await m.evaluate("document.body.innerText")
            await m.screenshot(path=f"s_{shot}.png")
            bad = [l for l in LOG if any(k in l for k in BAD)]
            results[name] = ("OK" if (wait_text in body and not bad) else f"CHECK text={wait_text in body} bad={bad[:2]}")
            print(f"{name:22s} {results[name]}")
        async def back():
            await m.get_by_role("button", name="Back").first.click()
            await m.wait_for_timeout(800)

        # tabs
        for tab, key, shot in [("Gallery","Upload photos","gallery"),("Scan","Navratri","scan"),("My Passes","Navratri","passes")]:
            await visit(tab, lambda t=tab: m.get_by_role("tab", name=t).click(), key, shot)
        await m.get_by_role("tab", name="Manage").click(); await m.wait_for_timeout(1500)
        await m.screenshot(path="s_manage.png")
        # manage items
        items = [("Payment approvals","To review","approvals"),("Events","Navratri","manage_events"),("Members","Requests","members"),
                 ("Photo moderation","Photo moderation","moderation"),("Invite residents","Invite code","invite"),("Society settings","Danger zone","society")]
        for label, key, shot in items:
            await visit(label, lambda l=label: m.get_by_role("button", name=l, exact=False).first.click(), key, shot)
            await back()
        # event admin → form → report
        await m.get_by_role("button", name="Events", exact=False).first.click(); await m.wait_for_timeout(1500)
        await visit("event admin", lambda: m.get_by_role("button", name="Navratri", exact=False).first.click(), "Gate volunteers", "event_admin")
        await visit("event form (edit)", lambda: m.get_by_role("button", name="Edit", exact=True).first.click(), "Pass tiers", "event_form")
        await back()
        await visit("report", lambda: m.get_by_role("button", name="Report", exact=True).first.click(), "By tier", "report")
        print("console noise:", [l for l in LOG if "GL Driver" not in l and "Injecting" not in l][:5])
        await b.close()
asyncio.run(run())
