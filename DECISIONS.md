# Decisions

Decisions made autonomously while building (newest at bottom of each section).

## Data model changes vs. the brief
- **UUID primary keys** everywhere (non-enumerable ids; safer for a multi-tenant API). `audit_logs.id` is a bigserial.
- **`*_url` columns store storage keys** (`banner_key`, `logo_key`, `screenshot_key`, `url_key`, `thumb_key`, `avatar_key`);
  the API resolves them into URLs (`*_url`). Public objects get a plain URL, private ones (payment screenshots) a
  short-lived presigned GET.
- `users.is_super_admin` flag instead of a `super_admin` membership role — super admin is platform-wide, not per society.
- Added tables: `otp_codes`, `refresh_tokens` (rotation + reuse detection), `push_tokens`, `preapproved_members`
  (CSV auto-approve), `pass_tier_days` (which days a "specific" tier is valid), `uploads` (presign bookkeeping).
- Added columns: `societies.timezone`, `orders.ref_code` (human reference used as the UPI note), `orders.paid_amount`
  (amount the member claims to have paid → drives the amount-mismatch flag), `orders.payment_submitted_at`,
  `orders.flags` (jsonb), `order_items.holders` (names/types captured before approval), `passes.event_id/society_id/user_id`
  (denormalised for scoping + fast scan queries), `pass_scans.client_ref` (retry-safe scans), `events.payment_provider`,
  `events.reminder_sent_at`, `gallery_items.moderated_by`.
- Roles are stored per society in `memberships.role` (`owner|admin|volunteer|member`); a member who is rejected or removed
  gets `status=removed` (and may re-request).

## Auth
- Phone numbers are normalised to E.164 (bare 10-digit numbers default to +91).
- OTPs are stored HMAC-hashed, 5-minute TTL, max 5 attempts, per-phone limits (5/hour + 30s cooldown) enforced in the DB
  (valid across workers) plus a per-IP in-memory limiter.
- Refresh tokens are rotated on every use; replaying an already-rotated token revokes all of that user's sessions.
- Dev conveniences `OTP_FIXED_CODE` and `OTP_DEV_ECHO` are ignored when `ENV=prod`.

## Tenancy & roles
- Every society-scoped route lives under `/societies/{society_id}/...` and uses the `require_role()` dependency, which
  loads the caller's membership from the DB. Non-members get **404** (society existence isn't leaked); pending/removed
  members and insufficient roles get **403**. Child resources are always looked up with both id *and* society_id.
- Role hierarchy: member < volunteer < admin < owner. Owner manages everyone except owners; admins manage only
  members/volunteers. The owner role can't be assigned or changed through the API (no ownership transfer in the MVP).
- "Min 2 admins" is a **warning** (`min_two_admins`) returned to owners/admins on society detail and after role
  changes — not a hard block, as specified.
- "Delete society" is a soft delete (`status=deleted`) that hides it from everyone; it requires typing the society name.
- Suspended societies: every society-scoped route returns 403 `society_suspended` (except reading the society and
  leaving/deleting).

## Uploads / storage
- Clients upload via presigned PUT to a **private `raw/` object**; the API then validates (Pillow), strips EXIF,
  resizes, and writes the final object (public bucket for banners/logos/gallery/avatars, private for payment
  screenshots). Unvalidated bytes are never served. An `uploads` row ties each presign to user + society + purpose and
  is single-use.
- Public assets live in a public-read bucket under unguessable UUID keys (so RN image caching works); this is a
  conscious trade-off — anyone holding a URL can view that image. Payment screenshots never go there.
- A `local` storage backend (filesystem, served by the API with HMAC-signed URLs) exists for dev/tests so the stack runs
  without MinIO.

## Mobile: Flutter (changed mid-build at the owner's request)
- The first mobile implementation was Expo/React Native; it was **replaced by a Flutter app** (`/mobile`) with the same
  feature set. Nothing server-side depended on Expo except push, which moved to **FCM** (see below).
- State: **Riverpod 3** (`Notifier`/`FutureProvider`) + **go_router**. No code generation (plain Dart models) so
  `flutter pub get && flutter run` is all that's needed.
- Data freshness: a single `dataVersionProvider` is bumped after every mutation; every query provider and paged list
  watches it. Simple, predictable invalidation — chosen over per-query cache keys for an MVP-sized API.
- "Active society" is **derived** (stored id if still an active membership, else the first one). Writing auth state from
  a provider listener caused circular rebuilds and broken navigation (found by a real-browser run), so only explicit
  choices (switcher / create / join) are persisted.
- Offline "My Passes": the pass list is cached in `shared_preferences` per user on every successful fetch; on a
  network error the screen falls back to the cache and shows an "offline" banner. QR codes render purely from the cached
  signed token, so entry works with no signal. Scanning itself needs the API (the server is the only verifier).
- i18n: a small key→string table (`en` complete, `hi`/`gu` for the core flows, English fallback) with `{{placeholder}}`
  interpolation — chosen over ARB codegen to keep the toolchain trivial. Unit tests enforce that every `t('key')` used in
  code exists in English and that hi/gu keys/placeholders match. Noto Sans (Latin / Gujarati / Devanagari) via `google_fonts`.
- UPI: the app opens the `upi://pay?...` link the API builds (payee, amount, note = order reference). Android 11+ needs
  the `<queries>` entry for the `upi` scheme (added); iOS lists UPI schemes in `LSApplicationQueriesSchemes`.
- Release builds must use HTTPS: cleartext HTTP is enabled only in Android debug/profile manifests.
- Verification: unit + widget tests, a **live-API contract test** (Dart client + models vs a running seeded backend), and
  the app was also built for web and driven end-to-end in headless Chromium (login → buy → proof → admin approve → QR).
  Android/iOS binaries were not built in this environment (no SDKs).

## Push notifications
- Server side is a `PushProvider` interface: `log` (default in dev) and `fcm` (Firebase Cloud Messaging **HTTP v1**,
  service-account OAuth done with PyJWT — no firebase-admin dependency). Unregistered tokens are pruned automatically.
- Sends happen in `BackgroundTasks` with their own DB session, never inside the request transaction.
- The Flutter app registers its FCM token at `POST /me/push-tokens` and degrades gracefully when Firebase isn't configured.
- Events: join request / approved / rejected, order approved / rejected / expired, event published / cancelled,
  "event tomorrow" reminder (in-process hourly-ish job with an atomic claim so multiple workers don't double send),
  volunteer assigned, gallery awaiting review, society suspended.

## Payments & orders
- `PaymentProvider` interface; `manual_upi` is live, `razorpay` is a documented stub (not registrable on events).
- Flow = **create order → pay in any UPI app → submit proof (screenshot and/or 12-digit UTR) → admin review**. Orders
  only enter the admin queue once proof is submitted (`payment_submitted_at`).
- Capacity is reserved from order creation: approved orders + pending orders that either have proof submitted or are
  younger than 48 h. **Unpaid** orders older than 48 h stop holding seats (lazily in every capacity query, and
  physically by a periodic job → `cancelled`, reason `expired`). Orders waiting on an admin never expire on the member.
- Seat accounting is race-free: tier rows are locked (`FOR UPDATE`, deterministic order) while an order is created;
  a test fires concurrent orders at the last seat.
- Auto-flags (stored on the order): `duplicate_utr` (platform-wide, flags the earlier order too), `amount_mismatch`
  (member's declared amount ≠ total), `missing_utr` (screenshot only). **Bulk approve skips flagged orders** unless the
  admin explicitly forces them; a single approve of a flagged order is allowed (admin's call) and audited with the flags.
- Free events / free tiers: orders with total 0 are auto-approved and passes issued immediately.

## Passes, QR & scanning
- QR token = `v1.<base64url(JSON{p: pass_id, e: event_id, n: nonce})>.<base64url(HMAC-SHA256)>` using `QR_SECRET`
  (constant-time compare). The DB row must also match the token, the pass must belong to the *scanner's* society, and be
  `active` with an `approved` order — so a pass from another society is indistinguishable from a forgery.
- Scan rules (server): pass valid for the event → event not cancelled/draft → today (society timezone) is an event day
  (an event running past midnight keeps the previous day for 2 h) → tier valid that day → one scan per pass per day via a
  unique constraint + `INSERT … ON CONFLICT DO NOTHING` (race-free; concurrent scans admit exactly once).
  Idempotent retries: an optional client-generated `client_ref` makes a retried request return the original "OK".
- Volunteers may scan only events they're assigned to; the assignment expires at event end + 6 h (and follows edits to
  the event end). Admins/owners can scan any event of their society.
- Live counters (scanned today / expected today / sold) come back with every scan and from `scan-stats`.

## Gallery
- Admin uploads are auto-approved; member uploads wait for moderation (cap of 50 pending per member). Thumbnails (480 px)
  and the full image (≤2048 px) are produced server-side with Pillow; **all EXIF/GPS is stripped** (re-encode to JPEG).
- Event galleries open to members only after the event ends (admins always); the society-wide gallery lists everything approved.

## Super admin
- Platform admins are `users.is_super_admin` (seeded via `SUPER_ADMIN_PHONES` on login or `python -m app.cli`).
  They have **no implicit society access** (society routes still 404 for them) and the platform API deliberately never
  returns payment screenshots.
- The web panel stores its session in `localStorage` (acceptable for an internal tool; put it behind SSO/VPN in production).

## Testing
- Backend: pytest + httpx against **real PostgreSQL** with the schema built by the actual Alembic migrations; every
  society-scoped route is discovered from the OpenAPI schema and swept for (a) 401 without auth, (b) 404 for non-members,
  (c) 403 for pending members — new routes are covered automatically. Object-level tests prove cross-tenant IDs can't be
  addressed through another society's URL. The S3 storage code path is exercised against an in-process `moto` S3 server.
- Only the *shape* of the migration is regenerated with `alembic revision --autogenerate`; a test run downgrades to base and
  upgrades to head every time.

## Known limitations (MVP)
- No ownership transfer; "owner" can't be reassigned through the API.
- No refunds flow (cancelled events tell admins refunds are manual).
- Gate scanning needs connectivity (by design — the server is the single source of truth for "already scanned").
- The in-process job loop runs in every API worker; claims are atomic but a dedicated worker/cron is better at scale.
- OTP delivery for MSG91 is a thin stub (DLT template registration and delivery webhooks are TODO).
