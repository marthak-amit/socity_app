import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api.dart';
import '../core/models.dart';
import '../core/storage.dart';
import '../core/utils.dart';
import 'auth.dart';

/// Bump after any mutation: every provider below re-fetches (simple, correct invalidation for an MVP-sized API).
class DataVersion extends Notifier<int> {
  @override
  int build() => 0;
  void bump() => state++;
}

final dataVersionProvider = NotifierProvider<DataVersion, int>(DataVersion.new);

final meProvider = FutureProvider<Me>((ref) async {
  ref.watch(dataVersionProvider);
  final token = ref.watch(authProvider.select((s) => s.accessToken));
  if (token == null) throw ApiError(401, 'not_authenticated', 'Not signed in');
  return Me.fromJson(await ref.watch(apiProvider).getJson('/me'));
});

/// The society the user is currently "in" + their role there (taken from the server's membership row).
class ActiveSociety {
  ActiveSociety({this.membership, this.me, this.loading = false, this.error});
  final Membership? membership;
  final Me? me;
  final bool loading;
  final Object? error;
  String? get societyId => membership?.society.id;
  Role? get role => membership?.role;
  SocietyBrief? get society => membership?.society;
  bool get suspended => society?.suspended ?? false;
  List<Membership> get memberships => me?.memberships ?? const [];
  List<Membership> get pending => memberships.where((m) => m.status == 'pending').toList();
  User? get user => me?.user;
}

final activeSocietyProvider = Provider<ActiveSociety>((ref) {
  final me = ref.watch(meProvider);
  final activeId = ref.watch(authProvider.select((s) => s.activeSocietyId));
  return me.when(
    data: (m) {
      final active = m.memberships.where((x) => x.active).toList();
      final current = active.where((x) => x.society.id == activeId).firstOrNull ?? active.firstOrNull;
      return ActiveSociety(membership: current, me: m);
    },
    loading: () => ActiveSociety(loading: true, me: me.value),
    error: (e, _) => ActiveSociety(error: e, me: me.value),
  );
});

final societyDetailProvider = FutureProvider.family<Society, String>((ref, id) async {
  ref.watch(dataVersionProvider);
  return Society.fromJson(await ref.watch(apiProvider).getJson('/societies/$id'));
});

final eventProvider = FutureProvider.family<EventT, ({String sid, String id})>((ref, a) async {
  ref.watch(dataVersionProvider);
  return EventT.fromJson(await ref.watch(apiProvider).getJson('/societies/${a.sid}/events/${a.id}'));
});

final orderProvider = FutureProvider.family<Order, ({String sid, String id})>((ref, a) async {
  ref.watch(dataVersionProvider);
  return Order.fromJson(await ref.watch(apiProvider).getJson('/societies/${a.sid}/orders/${a.id}'));
});

final orderSummaryProvider = FutureProvider.family<OrderSummary, String>((ref, sid) async {
  ref.watch(dataVersionProvider);
  return OrderSummary.fromJson(await ref.watch(apiProvider).getJson('/societies/$sid/orders/summary'));
});

/// total for a list endpoint (badge counts), fetched with limit=1.
final countProvider = FutureProvider.family<int, ({String path, Map<String, String> query})>((ref, a) async {
  ref.watch(dataVersionProvider);
  final j = await ref.watch(apiProvider).getJson(a.path, query: {...a.query, 'limit': 1});
  return (j['total'] as num).toInt();
});

final reportProvider = FutureProvider.family<Report, ({String sid, String id})>((ref, a) async {
  ref.watch(dataVersionProvider);
  return Report.fromJson(await ref.watch(apiProvider).getJson('/societies/${a.sid}/events/${a.id}/report'));
});

final volunteersProvider = FutureProvider.family<List<Volunteer>, ({String sid, String id})>((ref, a) async {
  ref.watch(dataVersionProvider);
  return (await ref.watch(apiProvider).getList('/societies/${a.sid}/events/${a.id}/volunteers')).map((e) => Volunteer.fromJson(e as Json)).toList();
});

final inviteProvider = FutureProvider.family<Invite, String>((ref, sid) async {
  ref.watch(dataVersionProvider);
  return Invite.fromJson(await ref.watch(apiProvider).getJson('/societies/$sid/invite'));
});

final scanEventsProvider = FutureProvider.family<List<ScanEvent>, String>((ref, sid) async {
  ref.watch(dataVersionProvider);
  return (await ref.watch(apiProvider).getList('/societies/$sid/scan/events')).map((e) => ScanEvent.fromJson(e as Json)).toList();
});

// ---------------------------------------------------------------------------------------------- my passes (offline-first)
final passCacheProvider = Provider<PassCache>((ref) => PassCache(ref.watch(prefsStoreProvider)));

class PassesResult {
  PassesResult(this.passes, {this.offline = false, this.savedAt});
  final List<PassT> passes;
  final bool offline;
  final DateTime? savedAt;
}

/// Passes from the API; with no connection, falls back to the copy saved on this phone so QR codes still work.
final myPassesProvider = FutureProvider<PassesResult>((ref) async {
  ref.watch(dataVersionProvider);
  final user = ref.watch(authProvider.select((s) => s.user));
  if (user == null) return PassesResult(const []);
  final api = ref.watch(apiProvider);
  final cache = ref.watch(passCacheProvider);
  try {
    final raw = <Json>[];
    for (var offset = 0; offset < 1000; offset += 100) {
      final page = await api.getJson('/me/passes', query: {'limit': 100, 'offset': offset});
      raw.addAll((page['items'] as List).cast<Json>());
      if (raw.length >= (page['total'] as num)) break;
    }
    await cache.save(user.id, raw);
    return PassesResult(raw.map(PassT.fromJson).toList());
  } on ApiError catch (e) {
    if (e.isNetwork) {
      final cached = await cache.load(user.id);
      if (cached != null) return PassesResult(cached.passes.map(PassT.fromJson).toList(), offline: true, savedAt: cached.savedAt);
    }
    rethrow;
  }
});

String prettyJson(Object o) => const JsonEncoder.withIndent(' ').convert(o);
