# Progress

- [x] **M1** Repo structure, docker-compose, backend skeleton, DB models, Alembic migration, auth (OTP+JWT), health check, seed script
- [x] **M2** Societies, memberships, roles, invite/join/approve, CSV pre-approval, scoping tests
- [x] **M3** Events, days, tiers, volunteers, banner upload (presigned → validated → EXIF-stripped), reminders
- [x] **M4** Orders, screenshot upload, approval queue, flags, bulk approve, pass generation, signed QR, expiry job
- [x] **M5** Scanning (idempotent, per-day, volunteer assignment), live counters, reports + CSV/XLSX export
- [x] **M6** Gallery + moderation + server-side thumbnails + EXIF stripping
- [x] **M7** Mobile app — **Flutter** (switched from Expo): all roles/screens wired to the API, role-based tabs, society switcher,
      offline passes, scanner, FCM push, i18n (en/gu/hi)
- [x] **M8** Super-admin web panel (societies, suspend, stats, flagged orders, audit logs)
- [x] **M9** Full test pass, demo seed (2 societies, 5 events incl. 9-day Navratri, every role), README, API docs at `/docs`, CI

## Verification log
- Backend: pytest (real PostgreSQL via Alembic migrations) — tenant-isolation sweep over every society route, concurrency
  (last seat, simultaneous scans), S3 path against moto, FCM v1 payloads, reports/exports, scanning rules incl. multi-day.
- Mobile: `flutter analyze` clean; unit + widget + router tests; **live contract test** against the seeded API;
  the app was also compiled for web and driven end to end in headless Chromium (login → buy → UPI proof → admin approve → QR).
- Admin web: vitest + production build; driven in headless Chromium against the live API (login, suspend/reinstate, flagged, audit).
- Not verifiable here: Android/iOS binaries (no SDKs), real FCM delivery, real UPI apps, Docker (no daemon) — compose file validated with `docker compose config`.
