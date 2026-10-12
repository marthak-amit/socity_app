import asyncio, random
import os
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "purchase_flow.py")).read().split("async def main")[0])

async def fill(page, label, value):
    tb = page.get_by_role("textbox", name=label, exact=False).first
    await tb.click(force=True); await page.wait_for_timeout(300)
    await page.keyboard.type(value, delay=15)

async def run():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=["--no-sandbox", "--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        n = random.randint(10000, 99999)
        owner_phone, joiner_phone = f"98{n}001", f"98{n}002"
        # ---- brand-new user → profile setup → onboarding → create society
        o = await login(b, owner_phone)
        await text(o, "What should we call you?")
        await type_into(o, 0, "Nirav Owner")   # autofocus name field
        await tap(o, "Continue")
        await text(o, "Create a society", timeout=20000)
        print("1 profile saved → onboarding shown")
        await tap(o, "Create a society", exact=False)
        await o.wait_for_timeout(1500)
        await o.screenshot(path="o_create.png")
        print((await o.evaluate("document.body.innerText"))[:300].replace("\n"," | "))
        await o.get_by_role("textbox", name="Society name", exact=False).first.wait_for(state="attached")
        await fill(o, "Society name", "Lotus Heights")
        await fill(o, "City", "Vadodara")
        await fill(o, "Society UPI ID", "lotus@okicici")
        await tap(o, "Create society")
        await text(o, "Invite code", timeout=20000)
        import subprocess
        code = [subprocess.check_output(["psql", "postgresql://societypass:societypass@localhost/societypass", "-tAc", "select invite_code from societies where name='Lotus Heights' order by created_at desc limit 1"]).decode().strip()]
        print("2 society created, invite code:", code[:1])
        # ---- second user joins with the code
        j = await login(b, joiner_phone)
        await text(j, "What should we call you?")
        await type_into(j, 0, "Jaya Joiner")
        await tap(j, "Continue")
        await tap(j, "Join a society", exact=False)
        await j.get_by_role("textbox", name="Invite code", exact=False).first.wait_for(state="attached")
        await fill(j, "Invite code", code[0])
        await tap(j, "Find society")
        await text(j, "Lotus Heights")
        await fill(j, "101", "301")
        await tap(j, "Request to join")
        await j.wait_for_timeout(2500)
        await j.screenshot(path="o_join.png")
        print((await j.evaluate("document.body.innerText"))[:300].replace("\n"," | "))
        await j.get_by_role("button", name="Check status").wait_for(state="attached", timeout=20000)
        print("3 join request sent → pending screen")
        # ---- owner approves in Members
        await o.keyboard.press("Escape")
        await o.get_by_role("button", name="Back").first.click(); await o.wait_for_timeout(1000)
        await o.get_by_role("tab", name="Manage").wait_for(state="attached", timeout=20000)
        await o.get_by_role("tab", name="Manage").click(); await o.wait_for_timeout(1000)
        await tap(o, "Members", exact=False)
        await o.wait_for_timeout(2500)
        await o.screenshot(path="o_members.png")
        print((await o.evaluate("document.body.innerText"))[:300].replace("\n"," | "))

        await tap(o, "Approve")
        await o.wait_for_timeout(1500)
        print("4 owner approved")
        await j.get_by_role("button", name="Check status").click()
        await j.wait_for_timeout(4000)
        await j.screenshot(path="o_joiner_after.png")
        print((await j.evaluate("document.body.innerText"))[:200].replace("\n"," | "))
        await j.get_by_role("tab", name="Events").wait_for(state="attached", timeout=20000)
        print("5 joiner now sees the society (tabs):", [t for t in ["Events","My Passes","Gallery","Scan","Manage"] if await j.get_by_role("tab", name=t).count()])
        await j.screenshot(path="o_joiner_home.png")
        print("console:", [l for l in LOG if any(k in l for k in ("FlutterError","Uncaught","Exception"))][:3])
        await b.close()
asyncio.run(run())
