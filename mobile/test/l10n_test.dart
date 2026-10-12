import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:societypass/l10n/strings.dart';
import 'package:societypass/l10n/strings_en.dart';
import 'package:societypass/l10n/strings_gu.dart';
import 'package:societypass/l10n/strings_hi.dart';

void main() {
  test('every static t(\'key\') used in the app exists in the English table', () {
    final missing = <String>[];
    final re = RegExp(r"\bt\(\s*'([a-zA-Z0-9_.]+)'");
    for (final f in Directory('lib').listSync(recursive: true).whereType<File>().where((f) => f.path.endsWith('.dart') && !f.path.contains('l10n'))) {
      for (final m in re.allMatches(f.readAsStringSync())) {
        final key = m.group(1)!;
        if (!stringsEn.containsKey(key)) missing.add('${f.path}: $key');
      }
    }
    expect(missing, isEmpty);
  });

  test('dynamically-built keys exist (t(\'group.\$value\'))', () {
    const need = {
      'roles': ['owner', 'admin', 'volunteer', 'member'],
      'common': ['pending', 'approved', 'rejected', 'cancelled'],
      'scan.result': ['ok', 'already_scanned', 'invalid_token', 'wrong_event', 'pass_revoked', 'event_not_active', 'not_event_day', 'tier_not_valid_today'],
      'approvals.flag': ['duplicate_utr', 'amount_mismatch', 'missing_utr'],
      'approvals.flagHelp': ['duplicate_utr', 'amount_mismatch', 'missing_utr'],
      'manage.warnings': ['min_two_admins', 'upi_not_configured'],
      'eventAdmin.statusLabel': ['draft', 'published', 'closed', 'cancelled'],
    };
    final missing = [for (final e in need.entries) for (final k in e.value) if (!stringsEn.containsKey('${e.key}.$k')) '${e.key}.$k'];
    expect(missing, isEmpty);
  });

  test('Hindi / Gujarati only define keys that exist in English and keep placeholders', () {
    String ph(String s) => (RegExp(r'\{\{\w+\}\}').allMatches(s).map((m) => m.group(0)!).toList()..sort()).join();
    for (final (name, table) in [('hi', stringsHi), ('gu', stringsGu)]) {
      for (final e in table.entries) {
        expect(stringsEn.containsKey(e.key), isTrue, reason: '$name has unknown key ${e.key}');
        expect(ph(e.value), ph(stringsEn[e.key]!), reason: '$name placeholder mismatch in ${e.key}');
      }
    }
  });

  test('translator interpolates and falls back to English then to the key', () {
    expect(const Tr('en')('auth.otpSent', {'phone': '9876543210'}), 'We sent a 6-digit code to +91 9876543210');
    expect(const Tr('hi')('tabs.passes'), 'मेरे पास');
    expect(const Tr('hi')('order.noOrders'), stringsEn['order.noOrders']); // untranslated → English
    expect(const Tr('gu')('totally.unknown'), 'totally.unknown');
    expect(const Tr('xx')('common.cancel'), stringsEn['common.cancel']);
  });
}
