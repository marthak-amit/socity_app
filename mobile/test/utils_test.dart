import 'package:flutter_test/flutter_test.dart';
import 'package:societypass/core/storage.dart';
import 'package:societypass/core/utils.dart';

void main() {
  group('money', () {
    test('Indian digit grouping', () {
      expect(formatInr(0), '₹0');
      expect(formatInr(500), '₹500');
      expect(formatInr(1500), '₹1,500');
      expect(formatInr(123456), '₹1,23,456');
      expect(formatInr(1234567), '₹12,34,567');
      expect(formatInr(-2500), '-₹2,500');
    });
    test('free label', () {
      expect(priceLabel(0), 'Free');
      expect(priceLabel(300), '₹300');
    });
  });

  group('validation', () {
    test('Indian phone normalisation', () {
      expect(normalizeIndianPhone('98765 43210'), '9876543210');
      expect(normalizeIndianPhone('+91 98765-43210'), '9876543210');
      expect(normalizeIndianPhone('09876543210'), '9876543210');
      expect(normalizeIndianPhone('12345'), isNull);
      expect(normalizeIndianPhone('5876543210'), isNull);
    });
    test('UTR is exactly 12 digits', () {
      expect(isValidUtr('402611223344'), isTrue);
      expect(isValidUtr('4026 1122 3344'), isTrue);
      expect(isValidUtr('40261122334'), isFalse);
      expect(isValidUtr('40261122334A'), isFalse);
      expect(sanitizeUtr('40a26-11223344999'), '402611223344');
    });
    test('UPI id and OTP', () {
      expect(isValidUpiId('greenvalley@okhdfc'), isTrue);
      expect(isValidUpiId('not-a-upi'), isFalse);
      expect(isValidOtp('123456'), isTrue);
      expect(isValidOtp('12345'), isFalse);
    });
  });

  test('invite links', () {
    expect(parseInviteCode('societypass://join?code=abcd2345'), 'ABCD2345');
    expect(parseInviteCode('https://societypass.app/join/ABCD2345'), 'ABCD2345');
    expect(parseInviteCode(' abcd2345 '), 'ABCD2345');
    expect(parseInviteCode('https://example.com/nothing'), isNull);
    expect(parseInviteCode(''), isNull);
  });

  group('roles', () {
    test('tabs by role', () {
      expect(tabsForRole(Role.member), [TabKey.events, TabKey.passes, TabKey.gallery]);
      expect(tabsForRole(Role.volunteer), [TabKey.events, TabKey.passes, TabKey.gallery, TabKey.scan]);
      expect(tabsForRole(Role.admin), [TabKey.events, TabKey.passes, TabKey.gallery, TabKey.scan, TabKey.manage]);
      expect(tabsForRole(Role.owner), contains(TabKey.manage));
      expect(tabsForRole(null), [TabKey.events, TabKey.passes, TabKey.gallery]);
    });
    test('assignable roles mirror the server', () {
      expect(assignableRoles(Role.owner, Role.member), [Role.admin, Role.volunteer]);
      expect(assignableRoles(Role.admin, Role.member), [Role.volunteer]);
      expect(assignableRoles(Role.admin, Role.admin), isEmpty);
      expect(assignableRoles(Role.owner, Role.owner), isEmpty);
      expect(assignableRoles(Role.volunteer, Role.member), isEmpty);
    });
  });

  group('dates', () {
    test('plain day strings round-trip', () {
      expect(toDayString(parseDay('2026-10-12')), '2026-10-12');
      expect(parseDay('2026-03-01').day, 1);
    });
    test('ranges', () {
      expect(formatDateRange(DateTime(2026, 10, 12, 10), DateTime(2026, 10, 12, 20)), '12 Oct');
      expect(formatDateRange(DateTime(2026, 10, 12), DateTime(2026, 10, 20)), '12 – 20 Oct');
      expect(formatDateRange(DateTime(2026, 10, 30), DateTime(2026, 11, 2)), '30 Oct – 2 Nov');
    });
    test('time formatting', () {
      expect(formatTime(DateTime(2026, 1, 1, 0, 5)), '12:05 AM');
      expect(formatTime(DateTime(2026, 1, 1, 19, 30)), '7:30 PM');
    });
    test('order expiry countdown', () {
      final now = DateTime(2026, 10, 12);
      expect(formatCountdown(now.add(const Duration(minutes: 23)), now: now), '23m');
      expect(formatCountdown(now.add(const Duration(hours: 5, minutes: 5)), now: now), '5h 05m');
      expect(formatCountdown(now.subtract(const Duration(hours: 1)), now: now), 'expired');
    });
  });

  test('UPI link carries the order reference as the note', () {
    expect(
      buildUpiUri(pa: 'society@okhdfc', pn: 'Green Valley', am: 1000, tn: 'Order SP-ABCD2345'),
      'upi://pay?pa=society%40okhdfc&pn=Green%20Valley&am=1000.00&cu=INR&tn=Order%20SP-ABCD2345',
    );
  });

  group('offline pass cache', () {
    test('saves and loads per user, never leaks across users', () async {
      final cache = PassCache(MemoryStore());
      await cache.save('u1', [
        {'id': 'p1', 'qr_token': 'v1.a.b'}
      ]);
      final c = await cache.load('u1');
      expect(c!.passes.single['qr_token'], 'v1.a.b');
      expect(await cache.load('u2'), isNull);
      await cache.clear('u1');
      expect(await cache.load('u1'), isNull);
    });
    test('corrupt cache is empty', () async {
      final store = MemoryStore();
      await store.set('passes:v1:u1', '{not json');
      expect(await PassCache(store).load('u1'), isNull);
    });
  });
}
