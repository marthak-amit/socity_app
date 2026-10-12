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
