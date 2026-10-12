import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:societypass/core/api.dart';
import 'package:societypass/core/models.dart';
import 'package:societypass/core/push.dart';
import 'package:societypass/core/utils.dart';
import 'package:societypass/router.dart';
import 'package:societypass/screens/auth_screens.dart';
import 'package:societypass/screens/events_tab.dart';
import 'package:societypass/screens/home_shell.dart';
import 'package:societypass/screens/pass_screen.dart';
import 'package:societypass/state/providers.dart';

import 'helpers.dart';

void main() {
  setUpAll(() {
    registerFallbackValue((Json j) => EventT.fromJson(j));
  });

  group('LoginScreen', () {
    testWidgets('rejects an invalid number without calling the API', (tester) async {
      final api = MockApi();
      await tester.pumpWidget(harness(const LoginScreen(), overrides: [apiProvider.overrideWithValue(api)]));
      await tester.enterText(find.byType(TextField), '12345');
      await tester.tap(find.text('Send OTP'));
      await tester.pump();
      expect(find.text('Enter a valid 10-digit mobile number'), findsOneWidget);
      verifyNever(() => api.request(any(), any(), body: any(named: 'body'), auth: any(named: 'auth')));
    });

    testWidgets('sends the normalised number to the API', (tester) async {
      final api = MockApi();
      when(() => api.request('POST', '/auth/otp/request', body: any(named: 'body'), auth: false)).thenThrow(ApiError(429, 'otp_cooldown', 'Wait'));
      await tester.pumpWidget(harness(const LoginScreen(), overrides: [apiProvider.overrideWithValue(api)]));
      await tester.enterText(find.byType(TextField), '98765 43210');
      await tester.tap(find.text('Send OTP'));
      await tester.pumpAndSettle();
      verify(() => api.request('POST', '/auth/otp/request', body: {'phone': '9876543210'}, auth: false)).called(1);
      expect(find.text('Please wait before requesting another code.'), findsOneWidget); // translated server error code
    });
  });

  group('role-based navigation', () {
    for (final (role, tabs) in [
      (Role.member, ['Events', 'My Passes', 'Gallery']),
      (Role.volunteer, ['Events', 'My Passes', 'Gallery', 'Scan']),
      (Role.admin, ['Events', 'My Passes', 'Gallery', 'Scan', 'Manage']),
      (Role.owner, ['Events', 'My Passes', 'Gallery', 'Scan', 'Manage']),
    ]) {
      testWidgets('${role.name} sees ${tabs.length} tabs', (tester) async {
        await tester.pumpWidget(harness(const HomeShell(), overrides: [
          apiProvider.overrideWithValue(emptyApi()),
          activeSocietyProvider.overrideWithValue(activeAs(role)),
        ]));
        await tester.pump();
        final bar = find.byType(NavigationBar);
        expect(bar, findsOneWidget);
        for (final label in tabs) {
          expect(find.descendant(of: bar, matching: find.text(label)), findsOneWidget, reason: '${role.name} should see $label');
        }
        for (final hidden in ['Scan', 'Manage'].where((x) => !tabs.contains(x))) {
          expect(find.descendant(of: bar, matching: find.text(hidden)), findsNothing, reason: '${role.name} must not see $hidden');
        }
        // header shows the active society and the user's role in it
        expect(find.text('Green Valley'), findsWidgets);
        expect(find.textContaining(role.name[0].toUpperCase() + role.name.substring(1)), findsWidgets);
      });
    }

    testWidgets('empty events list shows the empty state', (tester) async {
      await tester.pumpWidget(harness(const EventsTab(), overrides: [
        apiProvider.overrideWithValue(emptyApi()),
        activeSocietyProvider.overrideWithValue(activeAs(Role.member)),
      ]));
      await tester.pumpAndSettle();
      expect(find.text('No upcoming events'), findsOneWidget);
    });

    testWidgets('suspended society shows the suspended notice instead of events', (tester) async {
      final suspended = ActiveSociety(
        membership: Membership(id: 'm', society: SocietyBrief(id: 's1', name: 'X', city: 'Y', status: 'suspended'), role: Role.member, status: 'active'),
        me: Me(User(id: 'u', phone: '+91'), []),
      );
      await tester.pumpWidget(harness(const EventsTab(), overrides: [apiProvider.overrideWithValue(emptyApi()), activeSocietyProvider.overrideWithValue(suspended)]));
      await tester.pump();
      expect(find.text('This society is suspended'), findsOneWidget);
    });
  });

  group('pass QR', () {
    testWidgets('renders the signed token as a QR and shows holder + tier', (tester) async {
      final pass = PassT.fromJson(passJson());
      await tester.pumpWidget(harness(Scaffold(body: PassCardView(pass: pass, index: 0, total: 3))));
      expect(find.byType(QrImageView), findsOneWidget);
      expect(find.byKey(const ValueKey('qr-v1.payload.signature')), findsOneWidget); // the QR encodes exactly the server-signed token
      expect(find.text('Meera Joshi'), findsOneWidget);
      expect(find.text('Navratri 2026'), findsOneWidget);
      expect(find.text('Pass 1 of 3'), findsOneWidget);
      expect(find.text('Valid all days'), findsOneWidget);
    });

    testWidgets('revoked passes are clearly marked', (tester) async {
      await tester.pumpWidget(harness(Scaffold(body: PassCardView(pass: PassT.fromJson(passJson(status: 'revoked')), index: 0, total: 1))));
      expect(find.text('REVOKED'), findsOneWidget);
    });
  });

  group('EventCard', () {
    testWidgets('shows "Sold out" when no tier has seats left', (tester) async {
      await tester.pumpWidget(harness(Scaffold(body: SingleChildScrollView(child: EventCard(event: EventT.fromJson(eventJson(remaining: 0)))))));
      expect(find.text('Sold out'), findsOneWidget);
    });
    testWidgets('shows the starting price otherwise', (tester) async {
      await tester.pumpWidget(harness(Scaffold(body: SingleChildScrollView(child: EventCard(event: EventT.fromJson(eventJson()))))));
      expect(find.text('From ₹800'), findsOneWidget);
      expect(find.text('Sold out'), findsNothing);
    });
    testWidgets('drafts are flagged for admins', (tester) async {
      await tester.pumpWidget(harness(Scaffold(body: SingleChildScrollView(child: EventCard(event: EventT.fromJson(eventJson(status: 'draft')))))));
      expect(find.text('Draft'), findsOneWidget);
    });
  });

  group('router redirects', () {
    String? r(String path, {bool loggedIn = true, bool hasName = true, bool known = true, bool hasSociety = true}) =>
        computeRedirect(uri: Uri.parse(path), loggedIn: loggedIn, hasName: hasName, societyKnown: known, hasSociety: hasSociety);

    test('signed-out users are sent to login', () {
      expect(r('/', loggedIn: false), '/login');
      expect(r('/manage/approvals', loggedIn: false), '/login');
      expect(r('/login', loggedIn: false), isNull);
    });
    test('signed-in users skip the auth pages', () => expect(r('/login'), '/'));
    test('users without a name set it first', () {
      expect(r('/', hasName: false), '/profile-setup');
      expect(r('/profile-setup', hasName: false), isNull);
    });
    test('users with no society go to onboarding, but only once /me is known', () {
      expect(r('/', hasSociety: false), '/onboarding');
      expect(r('/', hasSociety: false, known: false), isNull);
    });
    test('onboarding is skipped when you already have a society unless adding another', () {
      expect(r('/onboarding'), '/');
      expect(r('/onboarding?add=1'), isNull);
    });
    test('invite deep links open the join screen with the code', () {
      expect(r('societypass://join?code=ABCD2345', loggedIn: false), '/join?code=ABCD2345');
    });
  });

  test('notification taps route to the right screen', () {
    expect(routeForNotification({'type': 'order_approved'}), '/?tab=passes');
    expect(routeForNotification({'type': 'order_rejected', 'order_id': 'o1'}), '/order/o1');
    expect(routeForNotification({'type': 'event_published', 'event_id': 'e1'}), '/event/e1');
    expect(routeForNotification({'type': 'join_request'}), '/manage/members');
    expect(routeForNotification({'type': 'gallery_pending'}), '/manage/moderation');
    expect(routeForNotification({'type': 'volunteer_assigned'}), '/?tab=scan');
    expect(routeForNotification({}), '/');
  });
}
