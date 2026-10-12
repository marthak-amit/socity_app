import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:societypass/core/api.dart';
import 'package:societypass/core/models.dart';
import 'package:societypass/core/storage.dart';
import 'package:societypass/router.dart';
import 'package:societypass/state/auth.dart';

import 'helpers.dart';

void main() {
  testWidgets('real router: signed-in member lands on tabs and can open Settings / an event', (tester) async {
    final api = MockApi();
    when(() => api.getJson('/me')).thenAnswer((_) async => {
          'user': {'id': 'u1', 'phone': '+919800000015', 'name': 'Raj Mehta', 'locale': 'en', 'is_super_admin': false},
          'memberships': [
            {'id': 'm1', 'role': 'member', 'status': 'active', 'flat_no': '202', 'wing': 'B', 'society': {'id': 's1', 'name': 'Green Valley', 'city': 'Ahmedabad', 'logo_url': null, 'status': 'active'}}
          ],
        });
    when(() => api.page<EventT>(any(), any(), query: any(named: 'query'), limit: any(named: 'limit'), offset: any(named: 'offset')))
        .thenAnswer((_) async => PageData<EventT>([EventT.fromJson(eventJson())], 1, 20, 0));
    when(() => api.getJson('/societies/s1/events/e1')).thenAnswer((_) async => eventJson());
    when(() => api.page<GalleryItem>(any(), any(), query: any(named: 'query'), limit: any(named: 'limit'), offset: any(named: 'offset')))
        .thenAnswer((_) async => PageData<GalleryItem>([], 0, 30, 0));

    final secure = MemoryStore();
    await secure.set('sp_access', 'tok');
    await secure.set('sp_refresh', 'ref');
    final prefs = MemoryStore();
    await prefs.set('sp_user', '{"id":"u1","phone":"+919800000015","name":"Raj Mehta","avatar_url":null,"locale":"en","is_super_admin":false}');
    final container = ProviderContainer(overrides: [
      secureStoreProvider.overrideWithValue(secure),
      prefsStoreProvider.overrideWithValue(prefs),
      apiProvider.overrideWithValue(api),
    ]);
    addTearDown(container.dispose);
    await container.read(authProvider.notifier).hydrate();

    await tester.pumpWidget(UncontrolledProviderScope(container: container, child: Consumer(builder: (c, ref, _) => MaterialApp.router(routerConfig: ref.watch(routerProvider)))));
    await tester.pumpAndSettle();
    expect(find.text('Diwali Snehmilan'), findsOneWidget); // events tab for the active society

    await tester.tap(find.byTooltip('Settings'));
    await tester.pumpAndSettle();
    expect(find.text('Sign out'), findsWidgets); // settings screen is showing

    // back, then open the event
    final router = container.read(routerProvider);
    router.pop();
    await tester.pumpAndSettle();
    await tester.tap(find.text('Diwali Snehmilan'));
    await tester.pumpAndSettle();
    expect(find.text('Get passes'), findsOneWidget);
  });

  // Regression: after the OTP screen (reached via push) signs in, the app must land on a *clean* stack so that
  // later pushes (Settings, an event, ...) work. Found via a real-browser run.
  testWidgets('real router: login via OTP, then push screens', (tester) async {
    final api = MockApi();
    when(() => api.request('POST', '/auth/otp/request', body: any(named: 'body'), auth: false)).thenAnswer((_) async => {'sent': true, 'dev_otp': '123456'});
    when(() => api.request('POST', '/auth/otp/verify', body: any(named: 'body'), auth: false)).thenAnswer((_) async => {
          'access_token': 'a', 'refresh_token': 'r', 'token_type': 'bearer', 'expires_in': 1800, 'is_new_user': false,
          'user': {'id': 'u1', 'phone': '+919800000015', 'name': 'Raj Mehta', 'locale': 'en', 'is_super_admin': false},
        });
    when(() => api.getJson('/me')).thenAnswer((_) async => {
          'user': {'id': 'u1', 'phone': '+919800000015', 'name': 'Raj Mehta', 'locale': 'en', 'is_super_admin': false},
          'memberships': [
            {'id': 'm1', 'role': 'member', 'status': 'active', 'flat_no': '202', 'wing': 'B', 'society': {'id': 's1', 'name': 'Green Valley', 'city': 'Ahmedabad', 'logo_url': null, 'status': 'active'}}
          ],
        });
    when(() => api.page<EventT>(any(), any(), query: any(named: 'query'), limit: any(named: 'limit'), offset: any(named: 'offset')))
        .thenAnswer((_) async => PageData<EventT>([EventT.fromJson(eventJson())], 1, 20, 0));
    final container = ProviderContainer(overrides: [
      secureStoreProvider.overrideWithValue(MemoryStore()),
      prefsStoreProvider.overrideWithValue(MemoryStore()),
      apiProvider.overrideWithValue(api),
    ]);
    addTearDown(container.dispose);
    await container.read(authProvider.notifier).hydrate();
    await tester.pumpWidget(UncontrolledProviderScope(container: container, child: Consumer(builder: (c, ref, _) => MaterialApp.router(routerConfig: ref.watch(routerProvider)))));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), '9800000015');
    await tester.tap(find.text('Send OTP'));
    await tester.pumpAndSettle();
    expect(find.text('Verify your number'), findsOneWidget);
    await tester.tap(find.widgetWithText(FilledButton, 'Verify'));
    await tester.pumpAndSettle();
    expect(find.text('Diwali Snehmilan'), findsOneWidget);
    expect(find.text('Verify your number'), findsNothing, reason: 'the OTP page must be gone from the stack');

    await tester.tap(find.byTooltip('Settings'));
    await tester.pumpAndSettle();
    expect(find.text('Sign out'), findsWidgets);
  });
}
