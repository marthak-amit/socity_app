# SocietyPass

Multi-tenant platform for Indian housing societies to run events and sell passes. Every society is an isolated space;
members pay the society's UPI ID, upload proof, an admin approves, the member gets a signed QR pass, volunteers scan it at
the gate, and past events keep a photo gallery.

| Part | Stack | Folder |
|---|---|---|
| API | Python 3.12 · FastAPI · SQLAlchemy 2 (async) · Alembic · PostgreSQL 16 · Pydantic v2 | [`backend/`](backend) |
| Mobile app (all roles) | **Flutter** (Riverpod, go_router) | [`mobile/`](mobile) |
| Super-admin panel | React · Vite · TypeScript · Tailwind | [`admin-web/`](admin-web) |
| Storage | S3-compatible: MinIO locally, Cloudflare R2 in prod (presigned uploads) | `docker-compose.yml` |

Out of scope by design: reels/videos, public feed, ads, chat.
Design notes and every judgment call live in [`DECISIONS.md`](DECISIONS.md); progress in [`PROGRESS.md`](PROGRESS.md).

## Quick start

```bash
cp .env.example .env                       # dev defaults work as-is (OTP is always 123456 in dev)
docker compose up --build                  # postgres, minio (+buckets), api on :8000, admin web on :5173
docker compose exec api python -m scripts.seed --reset     # demo data (2 societies, 5 events incl. a 9-day Navratri)
```

* API docs (Swagger): <http://localhost:8000/docs> · health: <http://localhost:8000/api/v1/health>
* Super-admin panel: <http://localhost:5173> · MinIO console: <http://localhost:9001> (minioadmin / minioadmin)
* Mobile app: see [`mobile/README.md`](mobile/README.md) — `cd mobile && flutter pub get && flutter run --dart-define=API_URL=http://<your-LAN-IP>:8000/api/v1`
  (a real phone must also reach MinIO: set `S3_PUBLIC_ENDPOINT_URL` / `S3_PUBLIC_BASE_URL` in `.env` to that LAN IP).

### Without Docker
```bash
cd backend && python3.12 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+asyncpg://user:pass@localhost/societypass STORAGE_BACKEND=local OTP_FIXED_CODE=123456 OTP_DEV_ECHO=true
alembic upgrade head && python -m scripts.seed --reset && uvicorn app.main:app --reload
```
`STORAGE_BACKEND=local` serves uploads from the filesystem through the API itself (HMAC-signed URLs) — no MinIO needed.

## Demo logins

Phone + OTP. In dev the OTP is **123456** (`OTP_FIXED_CODE`) and is echoed to the app (`OTP_DEV_ECHO`). Never set those in prod.

| Who | Phone | Role |
|---|---|---|
| Platform admin (web panel) | `9800000001` | super admin |
| Ramesh Patel | `9800000011` | **owner** · Green Valley Residency (invite code `GREEN123`) |
| Sunita Shah | `9800000012` | **admin** · Green Valley |
| Kiran Desai | `9800000013` | **volunteer** · Green Valley (assigned to Navratri) |
| Meera Joshi | `9800000014` | member in Green Valley, **admin** in Sunrise Heights → try the society switcher |
| Raj Mehta | `9800000015` | member · Green Valley (has approved passes) |
| Anita Verma | `9800000016` | pending join request (approve her in Manage → Members) |
| Neha Kapoor | `9800000040` | CSV-pre-approved: joins `GREEN123` and is auto-approved |
| Vikram Singh / Pooja Nair / Arjun Rao | `9800000031` / `32` / `33` | owner / admin / member · Sunrise Heights (`SUNRISE9`) |

Seed data also contains pending, flagged (duplicate UTR, amount mismatch, missing UTR), rejected and awaiting-payment orders,
tonight's gate scans, a past event with a photo gallery and photos waiting for moderation.

## Demo walkthrough (the definition of done)

1. **Create society** — new number → *Create a society* (add the UPI ID) → you are the owner; *Manage → Invite* shows the code + QR.
2. **Join** — another number → *Join a society* → enter/scan the code, wing & flat → *pending*; the owner approves in *Manage → Members*.
3. **Create event** — *Manage → Events → New event*: dates (multi-day gets one day per date), banner, tiers (price, capacity, per-person limit,
   valid days), then *Publish* (members get a push).
4. **Buy pass** — member opens the event → *Get passes* → quantity + holder names → *Pay via UPI app* (`upi://pay?…&tn=Order SP-XXXX`)
   → upload screenshot + 12-digit UTR. Seats are reserved while the order is pending.
5. **Approve** — *Manage → Payment approvals*: screenshot, amount, UTR, member & flat, auto-flags; approve/reject (with reason) or long-press to bulk-approve.
6. **QR pass** — *My Passes* shows the signed QR (cached, works offline). Pushed on approval.
7. **Scan** — volunteer/admin opens *Scan*, picks the event, scans: green/red with holder + tier, live "scanned / expected / sold".
8. **Report** — *Manage → Events → event → Report*: collected, by tier, by wing, by day; export CSV / XLSX.
9. **Gallery** — admins upload (auto-approved), members upload (moderation queue); an event's gallery opens to members after it ends.
10. **Platform** — super-admin panel: societies, suspend/reinstate, flagged orders across the platform, audit logs.

## Security model (summary)

* Roles live in `memberships(user, society, role, status)`; the server loads the caller's membership on **every** request — a client-supplied role is never used.
* Every society route is `/societies/{society_id}/…` behind one dependency: non-member → **404** (existence isn't leaked), pending/removed → 403, wrong role → 403, suspended society → 403.
  Child objects are always looked up by `(id, society_id)`. A test discovers every society route from the OpenAPI schema and sweeps it for auth/tenancy (new routes are covered automatically).
* Payment screenshots live in a **private** bucket and are only reachable through short-lived presigned URLs given to that society's admins (super admins don't get them either).
* Uploads: presigned PUT into a private `raw/` key → server validates with Pillow, re-encodes (EXIF stripped), enforces type/size, then publishes. Upload ids are single-use and bound to user + society + purpose.
* OTPs are HMAC-hashed, expire in 5 min, 5 attempts, per-phone + per-IP rate limits; refresh tokens rotate and replay revokes the family.
* QR tokens are HMAC-SHA256 signed; scanning validates signature, society, event, day, status and "already used" atomically.
* Every approve/reject, role change, removal, delete, suspension, UPI change and export is written to `audit_logs`.
* Secrets come from env (`.env.example`); the API refuses to boot in `ENV=prod` with the dev JWT/QR secrets.

## Tests

```bash
# backend (needs a PostgreSQL; creates the schema through the real Alembic migrations)
cd backend && pytest -q                                   # ~110 tests incl. tenant-isolation sweep, concurrency, S3 (moto), FCM, reports, scanning
ruff check app tests scripts
# mobile
cd mobile && flutter analyze && flutter test              # unit + widget + router tests (+ live contract test, see mobile/README.md)
# admin panel
cd admin-web && npm test && npm run build
```

## Repository map

```
backend/    app/{api/v1,core,models,schemas,services}  alembic/  scripts/seed.py  tests/
mobile/     Flutter app (lib/, test/, android/, ios/, web/)
admin-web/  React + Vite + Tailwind
docker-compose.yml  .env.example  DECISIONS.md  PROGRESS.md
```

## Production notes

* Set `ENV=prod`, strong `JWT_SECRET` / `QR_SECRET`, `OTP_PROVIDER=msg91` (+ keys), `STORAGE_BACKEND=s3` with R2 credentials
  (`S3_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com`, `S3_REGION=auto`, a public bucket domain for `S3_PUBLIC_BASE_URL`),
  `PUSH_PROVIDER=fcm`, restrictive `CORS_ORIGINS`, HTTPS everywhere. Run `alembic upgrade head` as a release step.
* Payment gateway: `PaymentProvider` is pluggable; `razorpay` is a stub with TODOs for Route/split payouts.
