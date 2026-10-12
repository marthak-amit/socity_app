import 'package:flutter/foundation.dart';

/// API base URL. Override at build/run time:
///   flutter run --dart-define=API_URL=http://192.168.1.20:8000/api/v1
/// Defaults: Android emulator → 10.0.2.2 (host loopback), everything else → localhost.
String apiBase() {
  const fromEnv = String.fromEnvironment('API_URL');
  if (fromEnv.isNotEmpty) return fromEnv.endsWith('/') ? fromEnv.substring(0, fromEnv.length - 1) : fromEnv;
  if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) return 'http://10.0.2.2:8000/api/v1';
  return 'http://localhost:8000/api/v1';
}

const appVersion = '0.1.0';
const deepLinkScheme = 'societypass';
