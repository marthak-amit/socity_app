# SocietyPass mobile (Flutter)

One app for every role (member · volunteer · admin · owner). Tabs and screens change with the role the **server** reports
for the active society; a society switcher in the header handles people who belong to several societies.

```
lib/
  main.dart · app.dart · router.dart      # bootstrap, theme, go_router + redirect rules
  core/    api.dart (HTTP + refresh rotation) · models.dart · utils.dart (money/validation/roles/dates) · storage.dart (offline pass cache) · push.dart (FCM)
  state/   auth.dart (tokens, active society, language) · providers.dart (queries; active society is derived)
  l10n/    strings_en.dart (complete) · strings_hi.dart · strings_gu.dart
  ui/      widgets.dart (design system) · paged.dart (infinite lists) · gallery_widgets.dart
  screens/ auth, onboarding, join (QR scan), events, buy, order (UPI + proof), passes (QR, offline), scan, gallery, manage/*
```

## Run it

```bash
cd mobile
flutter pub get
# Android emulator reaches the host as 10.0.2.2 (the default). For a real phone use your machine's LAN IP:
flutter run --dart-define=API_URL=http://192.168.1.20:8000/api/v1
# iOS simulator / desktop / web:  --dart-define=API_URL=http://localhost:8000/api/v1
flutter run -d chrome --dart-define=API_URL=http://localhost:8000/api/v1   # browser preview of the same app
```

Start the backend first (`docker compose up`, then `docker compose exec api python -m scripts.seed`) and sign in with
the demo numbers from the root README. With `OTP_DEV_ECHO=true` the OTP is pre-filled on the verify screen.

> Phones need to reach **MinIO** as well (photo uploads are presigned PUTs): set `S3_PUBLIC_ENDPOINT_URL` and
> `S3_PUBLIC_BASE_URL` in `.env` to your LAN IP, e.g. `http://192.168.1.20:9000`.

### Push notifications (optional)
Pushes use Firebase Cloud Messaging. Without Firebase config the app simply runs without them.
1. Create a Firebase project, add the Android (`app.societypass.mobile`) and iOS apps.
2. Drop `google-services.json` into `android/app/` and `GoogleService-Info.plist` into `ios/Runner/`
   (or run `flutterfire configure`), and apply the Google-services Gradle plugin.
3. Backend: set `PUSH_PROVIDER=fcm` and `FCM_SERVICE_ACCOUNT_FILE=/path/to/service-account.json`.

### Deep links
`societypass://join?code=GREEN123` opens the join screen with the code filled in (intent filter + URL scheme are configured);
the Invite screen shows that link as a QR code that the Join screen can scan.

## Tests

```bash
flutter analyze
flutter test                      # unit + widget tests (hermetic)
# contract test: the Dart client + models against a running, seeded backend
#   backend: OTP_FIXED_CODE=123456 OTP_DEV_ECHO=true OTP_RESEND_COOLDOWN_SECONDS=0 OTP_PER_PHONE_PER_HOUR=1000 uvicorn app.main:app
flutter test test/contract --dart-define=LIVE_API=true --dart-define=API_URL=http://localhost:8000/api/v1
```
