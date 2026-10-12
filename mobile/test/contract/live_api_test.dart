// Contract test: drives the Dart API client + models against a *running* backend seeded with `python -m scripts.seed`.
//
//   (backend) OTP_FIXED_CODE=123456 OTP_DEV_ECHO=true uvicorn app.main:app
//   flutter test test/contract --dart-define=LIVE_API=true --dart-define=API_URL=http://localhost:8000/api/v1
//   (flutter_test reports TargetPlatform.android, whose default API host is the emulator alias 10.0.2.2 — so pass API_URL.)
//
// Skipped automatically when LIVE_API is not set, so plain `flutter test` stays hermetic.
import 'dart:io';
import 'dart:math';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:societypass/core/api.dart';
import 'package:societypass/core/models.dart';
import 'package:societypass/core/storage.dart';
import 'package:societypass/core/utils.dart';
import 'package:societypass/state/auth.dart';
import 'package:societypass/state/providers.dart';

const live = bool.fromEnvironment('LIVE_API');

Future<ProviderContainer> signIn(String phone) async {
  final c = ProviderContainer(overrides: [
    secureStoreProvider.overrideWithValue(MemoryStore()),
    prefsStoreProvider.overrideWithValue(MemoryStore()),
  ]);
  final api = c.read(apiProvider);
  final req = await api.request('POST', '/auth/otp/request', body: {'phone': phone}, auth: false) as Json;
  final j = await api.request('POST', '/auth/otp/verify', body: {'phone': phone, 'code': (req['dev_otp'] ?? '123456') as String}, auth: false) as Json;
  await c.read(authProvider.notifier).setSession(j['access_token'], j['refresh_token'], User.fromJson(j['user']));
  await c.read(meProvider.future); // resolve /me so activeSocietyProvider has data
  return c;
}

void main() {
  setUpAll(() => HttpOverrides.global = null);

  group('live API', skip: live ? false : 'set --dart-define=LIVE_API=true', () {
    test('member: /me, society, events, event detail parse; active society + role resolve', () async {
      final c = await signIn('+919800000015'); // Raj Mehta
      addTearDown(c.dispose);
      final me = await c.read(meProvider.future);
      expect(me.user.name, 'Raj Mehta');
      final a = c.read(activeSocietyProvider);
      expect(a.society!.name, 'Green Valley Residency');
      expect(a.role, Role.member);
      expect(tabsForRole(a.role), isNot(contains(TabKey.manage)));

      final page = await c.read(apiProvider).page('/societies/${a.societyId}/events', EventT.fromJson, query: {'when': 'all'});
      expect(page.items.map((e) => e.title), containsAll(['Navratri Garba Mahotsav 2026', 'Diwali Snehmilan 2026']));
      final nav = page.items.firstWhere((e) => e.title.startsWith('Navratri'));
      expect(nav.days.length, 9);
      expect(nav.tiers.any((t) => t.validDays == 'specific' && t.dayIds.length == 1), isTrue);
      expect(nav.bookingOpen, isTrue);
      expect(nav.minPrice, 0); // free kids tier
      final detail = await c.read(eventProvider((sid: a.societyId!, id: nav.id)).future);
      expect(detail.tiers.length, nav.tiers.length);
    });

    test('member cannot reach admin endpoints (403) or other societies (404)', () async {
      final c = await signIn('+919800000015');
      addTearDown(c.dispose);
      final sid = c.read(activeSocietyProvider).societyId!;
      await expectLater(c.read(apiProvider).getJson('/societies/$sid/members'), throwsA(isA<ApiError>().having((e) => e.status, 'status', 403)));
      await expectLater(c.read(apiProvider).getJson('/societies/00000000-0000-0000-0000-000000000000'), throwsA(isA<ApiError>().having((e) => e.status, 'status', 404)));
      await expectLater(c.read(apiProvider).getJson('/admin/stats'), throwsA(isA<ApiError>().having((e) => e.code, 'code', 'super_admin_required')));
    });

    test('buy → pay proof → admin approve → QR pass → volunteer scan → report', () async {
      final member = await signIn('+919800000015');
      final admin = await signIn('+919800000012'); // Sunita (admin)
      final vol = await signIn('+919800000013'); // Kiran (volunteer, assigned)
      addTearDown(() {
        member.dispose();
        admin.dispose();
        vol.dispose();
      });
      final sid = member.read(activeSocietyProvider).societyId!;
      expect(admin.read(activeSocietyProvider).role, Role.admin);
      expect(tabsForRole(vol.read(activeSocietyProvider).role), contains(TabKey.scan));

      final events = await member.read(apiProvider).page('/societies/$sid/events', EventT.fromJson, query: {'when': 'upcoming'});
      final nav = events.items.firstWhere((e) => e.title.startsWith('Navratri'));
      final night = nav.tiers.firstWhere((t) => t.name == 'Single Night');
      final holderName = 'Contract Test ${Random().nextInt(100000)}';

      final order = Order.fromJson(await member.read(apiProvider).post('/societies/$sid/events/${nav.id}/orders', {
        'items': [
          {'tier_id': night.id, 'qty': 1, 'holders': [Holder(name: holderName).toJson()]}
        ]
      }));
      expect(order.status, 'pending');
      expect(order.payment!.upiUri, startsWith('upi://pay?'));
      expect(order.payment!.upiUri, contains('tn=Order%20${order.refCode}'));

      final utr = List.generate(12, (_) => Random().nextInt(10)).join();
      final paid = Order.fromJson(await member.read(apiProvider).post('/societies/$sid/orders/${order.id}/payment', {'utr': utr, 'paid_amount': 250}));
      expect(paid.submitted, isTrue);
      expect(paid.flags, isEmpty); // members never see flags/screenshots

      final queue = await admin.read(apiProvider).page('/societies/$sid/orders', Order.fromJson, query: {'status': 'pending', 'submitted': true}, limit: 50);
      final inQueue = queue.items.firstWhere((o) => o.id == order.id);
      expect(inQueue.utr, utr);
      expect(inQueue.member!.display, 'Raj Mehta');
      final summary = OrderSummary.fromJson(await admin.read(apiProvider).getJson('/societies/$sid/orders/summary'));
      expect(summary.pending, greaterThan(0));

      await admin.read(apiProvider).post('/societies/$sid/orders/${order.id}/approve');

      final passes = await member.read(apiProvider).page('/societies/$sid/passes/mine', PassT.fromJson, query: {'event_id': nav.id}, limit: 100);
      final pass = passes.items.firstWhere((p) => p.holderName == holderName);
      expect(pass.qrToken, startsWith('v1.'));
      expect(pass.status, 'active');

      // offline cache round trip uses the same JSON
      final cache = PassCache(MemoryStore());
      await cache.save('u', [pass.raw]);
      expect(PassT.fromJson((await cache.load('u'))!.passes.single).qrToken, pass.qrToken);

      final scan1 = ScanResult.fromJson(await vol.read(apiProvider).post('/societies/$sid/events/${nav.id}/scan', {'qr_token': pass.qrToken, 'client_ref': 'c-$utr'}));
      expect(scan1.ok, isTrue, reason: scan1.message);
      expect(scan1.holderName, holderName);
      final scan2 = ScanResult.fromJson(await vol.read(apiProvider).post('/societies/$sid/events/${nav.id}/scan', {'qr_token': pass.qrToken, 'client_ref': 'other'}));
      expect(scan2.ok, isFalse);
      expect(scan2.result, 'already_scanned');
      final forged = ScanResult.fromJson(await vol.read(apiProvider).post('/societies/$sid/events/${nav.id}/scan', {'qr_token': '${pass.qrToken}x'}));
      expect(forged.result, 'invalid_token');
      // a plain member can't scan
      await expectLater(member.read(apiProvider).post('/societies/$sid/events/${nav.id}/scan', {'qr_token': pass.qrToken}), throwsA(isA<ApiError>().having((e) => e.status, 'status', 403)));

      final report = Report.fromJson(await admin.read(apiProvider).getJson('/societies/$sid/events/${nav.id}/report'));
      expect(report.total('passes_sold'), greaterThan(0));
      expect(report.byTier, isNotEmpty);
      final csv = await admin.read(apiProvider).download('/societies/$sid/events/${nav.id}/report/export?format=csv');
      expect(String.fromCharCodes(csv), contains('Order ref'));
    });

    test('gallery models + moderation queue visible to admins only', () async {
      final admin = await signIn('+919800000012');
      final member = await signIn('+919800000015');
      addTearDown(() {
        admin.dispose();
        member.dispose();
      });
      final sid = admin.read(activeSocietyProvider).societyId!;
      final approved = await admin.read(apiProvider).page('/societies/$sid/gallery', GalleryItem.fromJson, limit: 30);
      expect(approved.total, greaterThanOrEqualTo(6));
      expect(approved.items.first.thumbUrl, startsWith('http'));
      final pending = await admin.read(apiProvider).page('/societies/$sid/gallery', GalleryItem.fromJson, query: {'status': 'pending'});
      expect(pending.items.every((g) => g.status == 'pending'), isTrue);
      await expectLater(member.read(apiProvider).getJson('/societies/$sid/gallery', query: {'status': 'pending'}), throwsA(isA<ApiError>().having((e) => e.status, 'status', 403)));
    });

    test('multi-society user has different roles per society', () async {
      final c = await signIn('+919800000014'); // Meera: member of Green Valley, admin of Sunrise Heights
      addTearDown(c.dispose);
      final me = await c.read(meProvider.future);
      final roles = {for (final m in me.memberships) m.society.name: m.role};
      expect(roles['Green Valley Residency'], Role.member);
      expect(roles['Sunrise Heights'], Role.admin);
      await c.read(authProvider.notifier).setActiveSociety(me.memberships.firstWhere((m) => m.society.name == 'Sunrise Heights').society.id);
      expect(c.read(activeSocietyProvider).role, Role.admin);
    });

    test('refresh-token rotation keeps the session alive after the access token is broken', () async {
      final c = await signIn('+919800000015');
      addTearDown(c.dispose);
      final auth = c.read(authProvider);
      await c.read(authProvider.notifier).setSession('garbage.access.token', auth.refreshToken!, auth.user!);
      final me = await c.read(apiProvider).getJson('/me'); // 401 → refresh → retry
      expect(me['user']['name'], 'Raj Mehta');
      expect(c.read(authProvider).accessToken, isNot('garbage.access.token'));
    });
  });
}
