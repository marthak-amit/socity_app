import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'screens/auth_screens.dart';
import 'screens/create_society_screen.dart';
import 'screens/event_detail_screen.dart';
import 'screens/buy_screen.dart';
import 'screens/home_shell.dart';
import 'screens/join_screen.dart';
import 'screens/manage/approvals_screen.dart';
import 'screens/manage/event_admin_screen.dart';
import 'screens/manage/event_form_screen.dart';
import 'screens/manage/invite_screen.dart';
import 'screens/manage/manage_events_screen.dart';
import 'screens/manage/members_screen.dart';
import 'screens/manage/moderation_screen.dart';
import 'screens/manage/report_screen.dart';
import 'screens/manage/society_settings_screen.dart';
import 'screens/onboarding_screen.dart';
import 'screens/order_screen.dart';
import 'screens/orders_screen.dart';
import 'screens/pass_screen.dart';
import 'screens/settings_screen.dart';
import 'state/auth.dart';
import 'state/providers.dart';

/// Bridges Riverpod state changes to go_router's refreshListenable.
class _RouterRefresh extends ChangeNotifier {
  _RouterRefresh(Ref ref) {
    ref.listen(authProvider, (_, _) => notifyListeners());
    ref.listen(activeSocietyProvider, (_, _) => notifyListeners());
  }
}

/// Pure redirect rules (unit-tested).
String? computeRedirect({
  required Uri uri,
  required bool loggedIn,
  required bool hasName,
  required bool societyKnown,
  required bool hasSociety,
}) {
  final path = uri.path;
  if (uri.scheme == 'societypass' && uri.host == 'join') {
    final code = uri.queryParameters['code'];
    return '/join${code != null ? '?code=$code' : ''}';
  }
  final authPage = path == '/login' || path == '/otp';
  if (!loggedIn) return authPage ? null : '/login';
  if (authPage) return '/';
  if (!hasName) return path == '/profile-setup' ? null : '/profile-setup';
  if (path == '/' && societyKnown && !hasSociety) return '/onboarding';
  if (path == '/onboarding' && hasSociety && uri.queryParameters['add'] == null) return '/';
  return null;
}

final routerProvider = Provider<GoRouter>((ref) {
  final refresh = _RouterRefresh(ref);
  ref.onDispose(refresh.dispose);

  return GoRouter(
    initialLocation: '/',
    refreshListenable: refresh,
    redirect: (context, state) {
      final auth = ref.read(authProvider);
      final active = ref.read(activeSocietyProvider);
      return computeRedirect(
        uri: state.uri,
        loggedIn: auth.loggedIn,
        hasName: (auth.user?.name ?? '').trim().isNotEmpty,
        societyKnown: !active.loading && active.error == null && active.me != null,
        hasSociety: active.societyId != null,
      );
    },
    routes: [
      GoRoute(path: '/', builder: (_, s) => HomeShell(initialTab: s.uri.queryParameters['tab'])),
      GoRoute(path: '/login', builder: (_, _) => const LoginScreen()),
      GoRoute(path: '/otp', builder: (_, s) => OtpScreen(phone: (s.extra as Map?)?['phone'] ?? '', devCode: (s.extra as Map?)?['dev'])),
      GoRoute(path: '/profile-setup', builder: (_, _) => const ProfileSetupScreen()),
      GoRoute(path: '/onboarding', builder: (_, _) => const OnboardingScreen()),
      GoRoute(path: '/join', builder: (_, s) => JoinScreen(code: s.uri.queryParameters['code'])),
      GoRoute(path: '/create-society', builder: (_, _) => const CreateSocietyScreen()),
      GoRoute(path: '/settings', builder: (_, _) => const SettingsScreen()),
      GoRoute(path: '/orders', builder: (_, _) => const OrdersScreen()),
      GoRoute(path: '/event/:id', builder: (_, s) => EventDetailScreen(id: s.pathParameters['id']!), routes: [
        GoRoute(path: 'buy', builder: (_, s) => BuyScreen(eventId: s.pathParameters['id']!)),
      ]),
      GoRoute(path: '/order/:id', builder: (_, s) => OrderScreen(id: s.pathParameters['id']!)),
      GoRoute(path: '/pass/:id', builder: (_, s) => PassScreen(id: s.pathParameters['id']!)),
      GoRoute(path: '/manage/events', builder: (_, _) => const ManageEventsScreen()),
      GoRoute(path: '/manage/event-form', builder: (_, s) => EventFormScreen(id: s.uri.queryParameters['id'])),
      GoRoute(path: '/manage/event/:id', builder: (_, s) => EventAdminScreen(id: s.pathParameters['id']!)),
      GoRoute(path: '/manage/report/:id', builder: (_, s) => ReportScreen(id: s.pathParameters['id']!)),
      GoRoute(path: '/manage/approvals', builder: (_, _) => const ApprovalsScreen(), routes: [
        GoRoute(path: ':id', builder: (_, s) => ApprovalDetailScreen(id: s.pathParameters['id']!)),
      ]),
      GoRoute(path: '/manage/members', builder: (_, _) => const MembersScreen()),
      GoRoute(path: '/manage/moderation', builder: (_, _) => const ModerationScreen()),
      GoRoute(path: '/manage/invite', builder: (_, _) => const InviteScreen()),
      GoRoute(path: '/manage/society', builder: (_, _) => const SocietySettingsScreen()),
    ],
  );
});
