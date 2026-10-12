import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Minimal key-value interface so the pass cache is testable without plugins.
abstract class KeyValueStore {
  Future<String?> get(String key);
  Future<void> set(String key, String value);
  Future<void> remove(String key);
}

class PrefsStore implements KeyValueStore {
  @override
  Future<String?> get(String key) async => (await SharedPreferences.getInstance()).getString(key);
  @override
  Future<void> set(String key, String value) async => (await SharedPreferences.getInstance()).setString(key, value);
  @override
  Future<void> remove(String key) async => (await SharedPreferences.getInstance()).remove(key);
}

/// Keychain / Keystore backed (tokens).
class SecureStore implements KeyValueStore {
  final _s = const FlutterSecureStorage();
  @override
  Future<String?> get(String key) => _s.read(key: key);
  @override
  Future<void> set(String key, String value) => _s.write(key: key, value: value);
  @override
  Future<void> remove(String key) => _s.delete(key: key);
}

class MemoryStore implements KeyValueStore {
  final Map<String, String> data = {};
  @override
  Future<String?> get(String key) async => data[key];
  @override
  Future<void> set(String key, String value) async => data[key] = value;
  @override
  Future<void> remove(String key) async => data.remove(key);
}

/// Offline copy of "My Passes" so QR codes still render with no signal.
class PassCache {
  PassCache(this.store);
  final KeyValueStore store;
  String _key(String userId) => 'passes:v1:$userId';

  Future<void> save(String userId, List<Map<String, dynamic>> passes) =>
      store.set(_key(userId), jsonEncode({'saved_at': DateTime.now().toUtc().toIso8601String(), 'passes': passes}));

  /// Returns null when there is no (valid) cache for *this* user.
  Future<({DateTime savedAt, List<Map<String, dynamic>> passes})?> load(String userId) async {
    try {
      final raw = await store.get(_key(userId));
      if (raw == null) return null;
      final m = jsonDecode(raw) as Map<String, dynamic>;
      return (
        savedAt: DateTime.parse(m['saved_at'] as String),
        passes: (m['passes'] as List).cast<Map<String, dynamic>>(),
      );
    } catch (_) {
      return null; // corrupt cache == empty
    }
  }

  Future<void> clear(String userId) => store.remove(_key(userId));
}
