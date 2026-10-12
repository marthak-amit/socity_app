import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/misc.dart' show Override;
import 'package:mocktail/mocktail.dart';
import 'package:societypass/core/api.dart';
import 'package:societypass/core/models.dart';
import 'package:societypass/core/storage.dart';
import 'package:societypass/core/utils.dart';
import 'package:societypass/state/auth.dart';
import 'package:societypass/state/providers.dart';

class MockApi extends Mock implements ApiClient {}

Membership membership({Role role = Role.member, String status = 'active', String name = 'Green Valley'}) => Membership(
      id: 'm1',
      society: SocietyBrief(id: 's1', name: name, city: 'Ahmedabad', status: 'active'),
      role: role,
      status: status,
    );

ActiveSociety activeAs(Role role) => ActiveSociety(
      membership: membership(role: role),
      me: Me(User(id: 'u1', phone: '+919800000015', name: 'Raj Mehta'), [membership(role: role)]),
    );

MockApi emptyApi() {
  final api = MockApi();
  when(() => api.page<EventT>(any(), any(), query: any(named: 'query'), limit: any(named: 'limit'), offset: any(named: 'offset')))
      .thenAnswer((_) async => PageData<EventT>([], 0, 20, 0));
  when(() => api.getJson(any(), query: any(named: 'query'))).thenAnswer((_) async => {'items': [], 'total': 0, 'limit': 1, 'offset': 0});
  return api;
}

Widget harness(Widget child, {List<Override> overrides = const []}) => ProviderScope(
      overrides: [
        secureStoreProvider.overrideWithValue(MemoryStore()),
        prefsStoreProvider.overrideWithValue(MemoryStore()),
        ...overrides,
      ],
      child: MaterialApp(home: child),
    );

Json passJson({String id = 'p1', String status = 'active', String holder = 'Meera Joshi', String tier = 'Season Pass', String token = 'v1.payload.signature'}) => {
      'id': id,
      'order_id': 'o1',
      'tier_id': 't1',
      'tier_name': tier,
      'holder_name': holder,
      'holder_type': 'member',
      'qr_token': token,
      'status': status,
      'valid_days': 'all',
      'valid_dates': <String>[],
      'scanned_dates': <String>[],
      'created_at': '2026-10-12T05:00:00+00:00',
      'event': {
        'id': 'e1',
        'society_id': 's1',
        'society_name': 'Green Valley',
        'title': 'Navratri 2026',
        'venue': 'Clubhouse',
        'starts_at': '2026-10-12T13:30:00+00:00',
        'ends_at': '2026-10-20T18:00:00+00:00',
        'banner_url': null,
      },
    };

Json eventJson({int remaining = 10, String status = 'published'}) => {
      'id': 'e1',
      'society_id': 's1',
      'title': 'Diwali Snehmilan',
      'description': null,
      'venue': 'Hall',
      'starts_at': '2026-11-05T12:30:00+00:00',
      'ends_at': '2026-11-05T16:30:00+00:00',
      'banner_url': null,
      'booking_deadline': null,
      'status': status,
      'is_paid': true,
      'payment_provider': 'manual_upi',
      'days': [
        {'id': 'd1', 'date': '2026-11-05', 'label': null}
      ],
      'tiers': [
        {
          'id': 't1', 'name': 'Family', 'description': null, 'price': 800, 'capacity': 80, 'per_user_limit': 3, 'valid_days': 'all',
          'day_ids': <String>[], 'allow_guests': true, 'sort_order': 0, 'sold': 0, 'pending': 0, 'remaining': remaining,
        }
      ],
      'booking_open': true,
      'is_over': false,
      'created_at': '2026-10-01T00:00:00+00:00',
    };
