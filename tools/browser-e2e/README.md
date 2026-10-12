# Browser end-to-end smoke scripts

These drive the **real apps against the real API** in headless Chromium (Playwright for Python). They are what backs the
"driven end to end in a browser" claims in `PROGRESS.md`. They are manual smoke tools, not part of CI.

Flutter web needs its semantics tree to be queryable, so the scripts click the hidden "enable accessibility" placeholder first.

```bash
# 1. API with relaxed OTP limits + seeded data
cd backend && OTP_FIXED_CODE=123456 OTP_DEV_ECHO=true OTP_RESEND_COOLDOWN_SECONDS=0 OTP_PER_PHONE_PER_HOUR=1000 OTP_PER_IP_PER_HOUR=100000 \
  STORAGE_BACKEND=local uvicorn app.main:app &     # and: python -m scripts.seed --reset
# 2. Flutter web build, served statically
cd mobile && flutter build web --no-web-resources-cdn --dart-define=API_URL=http://localhost:8000/api/v1
python -m http.server 8081 -d build/web &
# 3. run
pip install playwright && python tools/browser-e2e/purchase_flow.py       # member buys → admin approves → QR pass
python tools/browser-e2e/onboarding_flow.py                               # new user → create society → another joins → approved
python tools/browser-e2e/admin_screens_smoke.py                           # every admin/owner screen renders
CHROME_PATH=/path/to/chrome ...                                           # optional; defaults to Playwright's Chromium
```
`admin_panel.py` drives the React super-admin panel (`npm run dev`, default http://localhost:5173).
