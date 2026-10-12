import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../core/config.dart';
import '../core/models.dart';
import '../core/storage.dart';
import '../l10n/strings.dart';

final secureStoreProvider = Provider<KeyValueStore>((ref) => SecureStore());
final prefsStoreProvider = Provider<KeyValueStore>((ref) => PrefsStore());

class AuthState {
  const AuthState({this.ready = false, this.accessToken, this.refreshToken, this.user, this.activeSocietyId});
  final bool ready;
  final String? accessToken, refreshToken, activeSocietyId;
  final User? user;
  bool get loggedIn => accessToken != null;

  AuthState copyWith({bool? ready, String? accessToken, String? refreshToken, User? user, String? activeSocietyId, bool clearSession = false, bool clearSociety = false}) =>
      AuthState(
        ready: ready ?? this.ready,
        accessToken: clearSession ? null : (accessToken ?? this.accessToken),
        refreshToken: clearSession ? null : (refreshToken ?? this.refreshToken),
        user: clearSession ? null : (user ?? this.user),
        activeSocietyId: (clearSession || clearSociety) ? null : (activeSocietyId ?? this.activeSocietyId),
      );
}

const _kAccess = 'sp_access', _kRefresh = 'sp_refresh', _kUser = 'sp_user', _kSociety = 'sp_society', _kLocale = 'sp_locale';

class AuthController extends Notifier<AuthState> {
  KeyValueStore get _secure => ref.read(secureStoreProvider);
  KeyValueStore get _prefs => ref.read(prefsStoreProvider);

  @override
  AuthState build() => const AuthState();

  Future<void> hydrate() async {
    try {
      final access = await _secure.get(_kAccess);
      final refresh = await _secure.get(_kRefresh);
      final userRaw = await _prefs.get(_kUser);
      final society = await _prefs.get(_kSociety);
      final locale = await _prefs.get(_kLocale);
      if (locale != null) ref.read(langProvider.notifier).set(locale);
      state = AuthState(
        ready: true,
        accessToken: access,
        refreshToken: refresh,
        user: userRaw == null ? null : User.fromJson(jsonDecode(userRaw) as Json),
        activeSocietyId: society,
      );
    } catch (_) {
      state = const AuthState(ready: true);
    }
  }

  Future<void> setSession(String access, String refresh, User user) async {
    await _secure.set(_kAccess, access);
    await _secure.set(_kRefresh, refresh);
    await _prefs.set(_kUser, jsonEncode(user.toJson()));
    state = state.copyWith(accessToken: access, refreshToken: refresh, user: user);
    if (user.locale != 'en' && (await _prefs.get(_kLocale)) == null) ref.read(langProvider.notifier).set(user.locale);
  }

  Future<void> setUser(User user) async {
    await _prefs.set(_kUser, jsonEncode(user.toJson()));
    state = state.copyWith(user: user);
  }

  Future<void> logout() async {
    final refresh = state.refreshToken;
    state = state.copyWith(clearSession: true);
    await _secure.remove(_kAccess);
    await _secure.remove(_kRefresh);
    await _prefs.remove(_kUser);
    await _prefs.remove(_kSociety);
    if (refresh != null) {
      try {
        await http.post(Uri.parse('${apiBase()}/auth/logout'),
            headers: {'Content-Type': 'application/json'}, body: jsonEncode({'refresh_token': refresh}));
      } catch (_) {/* offline: server-side revoke is best effort */}
    }
  }

  Future<void> setActiveSociety(String? id) async {
    if (state.activeSocietyId == id) return;
    state = id == null ? state.copyWith(clearSociety: true) : state.copyWith(activeSocietyId: id);
    if (id == null) {
      await _prefs.remove(_kSociety);
    } else {
      await _prefs.set(_kSociety, id);
    }
  }

  Future<void> setLocale(String lang) async {
    ref.read(langProvider.notifier).set(lang);
    await _prefs.set(_kLocale, lang);
  }
}

final authProvider = NotifierProvider<AuthController, AuthState>(AuthController.new);
