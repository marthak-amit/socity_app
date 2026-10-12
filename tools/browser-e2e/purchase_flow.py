import asyncio, random, sys
from playwright.async_api import async_playwright

import os
BASE = os.environ.get("APP_URL", "http://localhost:8081")
CHROME = os.environ.get("CHROME_PATH") or None  # None → Playwright's own Chromium
LOG = []

async def new_page(browser):
    ctx = await browser.new_context(viewport={"width": 420, "height": 900})
    page = await ctx.new_page()
    page.on("pageerror", lambda e: LOG.append(f"pageerror: {e}"))
    page.on("console", lambda m: LOG.append(f"{m.type}: {m.text[:300]}"))
    await page.goto(BASE)
    await page.wait_for_selector("flt-glass-pane", state="attached", timeout=60000)
    await page.wait_for_timeout(2500)
    await page.evaluate("document.querySelector('flt-semantics-placeholder')?.click()")
    await page.wait_for_timeout(1000)
    return page

async def text(page, t, timeout=15000, exact=False):
    loc = page.get_by_text(t, exact=exact).first
    await loc.wait_for(state="attached", timeout=timeout)
    return loc

async def tap(page, t, exact=True, timeout=15000):
    try:
        await text(page, t, 2500, exact)
    except Exception:
        await page.get_by_role("tab", name=t, exact=exact).first.wait_for(state="attached", timeout=timeout)
    for role in ("button", "tab"):
        loc = page.get_by_role(role, name=t, exact=exact)
        if await loc.count():
            await loc.first.click()
            await page.wait_for_timeout(600)
            return
    await page.get_by_text(t, exact=exact).first.click(force=True)
    await page.wait_for_timeout(600)

async def type_into(page, idx, value):
    inp = page.locator("input, textarea").nth(idx)
    await inp.focus()
    await page.wait_for_timeout(300)
    await page.keyboard.type(value, delay=20)

async def login(browser, phone):
    page = await new_page(browser)
    await type_into(page, 0, phone)
    await tap(page, "Send OTP")
    await text(page, "Verify your number")
    await tap(page, "Verify")
    return page

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=["--no-sandbox", "--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        # ---------------- member buys a pass
        m = await login(b, "9800000015")                       # Raj Mehta (member)
        await text(m, "Navratri Garba Mahotsav 2026", timeout=30000)
        await m.screenshot(path="f_home.png")
        print("1 HOME OK (member tabs):", [t for t in ["Events","My Passes","Gallery","Scan","Manage"] if await m.get_by_role("tab", name=t).count()])
        await tap(m, "Navratri Garba Mahotsav 2026", exact=False)
        await text(m, "Get passes")
        await m.screenshot(path="f_event.png")
        await tap(m, "Get passes")
        await text(m, "Choose passes")
        await m.get_by_role("button", name="Increase Single Night").click(force=True)
        await m.wait_for_timeout(500)
        await m.screenshot(path="f_buy.png")   # first holder is pre-filled with the buyer's name
        await tap(m, "Continue to payment")
        await text(m, "Pay via UPI app", timeout=20000)
        await m.screenshot(path="f_order.png")
        body = await m.evaluate("document.body.innerText")
        print("2 ORDER: upi id shown:", "greenvalley@okhdfcbank" in body, "| ₹250:", "₹250" in body)
        utr = "".join(random.choice("0123456789") for _ in range(12))
        # fields on order screen: utr, amount paid
        tb = m.get_by_role("textbox", name="402611223344")
        await tb.click(force=True)
        await m.wait_for_timeout(400)
        await m.keyboard.type(utr, delay=20)
        await m.wait_for_timeout(400)
        await tap(m, "Submit for approval")
        await m.wait_for_timeout(2500)
        await m.screenshot(path="f_after_submit.png", full_page=False)
        print("   after submit:", (await m.evaluate("document.body.innerText"))[:500].replace("\n"," | "))
        await text(m, "Payment under review", timeout=15000)
        print("3 PROOF SUBMITTED, utr", utr)

        # ---------------- admin approves
        a = await login(b, "9800000012")                       # Sunita (admin)
        await a.get_by_role("tab", name="Manage").wait_for(state="attached", timeout=30000)
        print("4 ADMIN tabs:", [t for t in ["Events","My Passes","Gallery","Scan","Manage"] if await a.get_by_role("tab", name=t).count()])
        await tap(a, "Manage")
        await text(a, "Payment approvals")
        await a.screenshot(path="f_manage.png")
        await tap(a, "Payment approvals", exact=False)
        await text(a, utr, timeout=20000)
        await a.screenshot(path="f_queue.png")
        await tap(a, utr, exact=False)
        await text(a, "Payment proof")
        await a.screenshot(path="f_approval.png")
        await a.get_by_role("button", name="Approve", exact=True).click(force=True)
        await a.wait_for_timeout(800)
        await a.get_by_role("button", name="Approve").last.click(force=True)    # confirm dialog
        await a.wait_for_timeout(2000)
        print("5 APPROVED")

        # ---------------- member sees the QR pass
        await m.reload()
        await m.wait_for_selector("flt-glass-pane", state="attached")
        await m.wait_for_timeout(3000)
        await m.evaluate("document.querySelector('flt-semantics-placeholder')?.click()")
        await tap(m, "My Passes")
        await text(m, "Raj Mehta", timeout=20000)
        await m.screenshot(path="f_passes.png")
        await tap(m, "Raj Mehta", exact=False)
        await text(m, "Show this QR at the gate", timeout=15000)
        await m.screenshot(path="f_pass_qr.png")
        print("6 QR PASS SHOWN")
        print("errors:", LOG[:8])
        await b.close()
asyncio.run(main())
