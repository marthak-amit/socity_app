import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../state/auth.dart';
import '../state/providers.dart';
import 'api.dart';

final pushServiceProvider = Provider<PushService>((ref) => PushService(ref));

/// FCM push. Entirely best-effort: if Firebase isn't configured (no google-services.json /
/// GoogleService-Info.plist) or permission is denied, the app simply works without pushes.
class PushService {
  PushService(this._ref);
  final Ref _ref;
  bool _started = false;

  Future<void> start(GoRouter router) async {
    if (_started || kIsWeb) return;
    _started = true;
    try {
      await Firebase.initializeApp();
      final fcm = FirebaseMessaging.instance;
      final perm = await fcm.requestPermission();
      if (perm.authorizationStatus == AuthorizationStatus.denied) return;
      await _register(await fcm.getToken());
      fcm.onTokenRefresh.listen(_register);
      FirebaseMessaging.onMessage.listen((_) => _ref.read(dataVersionProvider.notifier).bump());
      FirebaseMessaging.onMessageOpenedApp.listen((m) => open(router, m.data));
      final initial = await fcm.getInitialMessage();
      if (initial != null) open(router, initial.data);
    } catch (e) {
      debugPrint('push disabled: $e');
    }
  }

  Future<void> _register(String? token) async {
    if (token == null) return;
    try {
      await _ref.read(apiProvider).post('/me/push-tokens', {'token': token, 'platform': defaultTargetPlatform.name});
    } catch (_) {}
  }

  /// Route a tapped notification to the right screen (switching society first when needed).
  Future<void> open(GoRouter router, Map<String, dynamic> data) async {
    final sid = data['society_id'] as String?;
    if (sid != null) await _ref.read(authProvider.notifier).setActiveSociety(sid);
    _ref.read(dataVersionProvider.notifier).bump();
    router.go(routeForNotification(data));
  }
}

String routeForNotification(Map<String, dynamic> d) {
  switch (d['type']) {
    case 'order_approved':
      return '/?tab=passes';
    case 'order_rejected':
      return d['order_id'] != null ? '/order/${d['order_id']}' : '/';
    case 'event_published' || 'event_reminder' || 'event_cancelled':
      return d['event_id'] != null ? '/event/${d['event_id']}' : '/';
    case 'join_request':
      return '/manage/members';
    case 'gallery_pending':
      return '/manage/moderation';
    case 'volunteer_assigned':
      return '/?tab=scan';
    default:
      return '/';
  }
}
