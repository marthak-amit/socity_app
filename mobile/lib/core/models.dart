import 'utils.dart';

typedef Json = Map<String, dynamic>;

DateTime _dt(dynamic v) => DateTime.parse(v as String).toLocal();
DateTime? _dtn(dynamic v) => v == null ? null : _dt(v);
int _i(dynamic v) => (v as num).toInt();
int? _in(dynamic v) => v == null ? null : _i(v);
List<T> _list<T>(dynamic v, T Function(Json) f) => ((v ?? const []) as List).map((e) => f(e as Json)).toList();

class PageData<T> {
  PageData(this.items, this.total, this.limit, this.offset);
  final List<T> items;
  final int total, limit, offset;
  factory PageData.fromJson(Json j, T Function(Json) f) =>
      PageData(_list(j['items'], f), _i(j['total']), _i(j['limit']), _i(j['offset']));
}

class User {
  User({required this.id, required this.phone, this.name, this.avatarUrl, this.locale = 'en', this.isSuperAdmin = false});
  final String id, phone, locale;
  final String? name, avatarUrl;
  final bool isSuperAdmin;
  factory User.fromJson(Json j) => User(
      id: j['id'], phone: j['phone'], name: j['name'], avatarUrl: j['avatar_url'], locale: j['locale'] ?? 'en',
      isSuperAdmin: j['is_super_admin'] ?? false);
  Json toJson() => {'id': id, 'phone': phone, 'name': name, 'avatar_url': avatarUrl, 'locale': locale, 'is_super_admin': isSuperAdmin};
}

class SocietyBrief {
  SocietyBrief({required this.id, required this.name, required this.city, this.logoUrl, required this.status});
  final String id, name, city, status;
  final String? logoUrl;
  factory SocietyBrief.fromJson(Json j) =>
      SocietyBrief(id: j['id'], name: j['name'], city: j['city'], logoUrl: j['logo_url'], status: j['status']);
  bool get suspended => status == 'suspended';
}

class Membership {
  Membership({required this.id, required this.society, required this.role, required this.status, this.flatNo, this.wing});
  final String id, status;
  final SocietyBrief society;
  final Role role;
  final String? flatNo, wing;
  factory Membership.fromJson(Json j) => Membership(
      id: j['id'], society: SocietyBrief.fromJson(j['society']), role: roleFrom(j['role']), status: j['status'],
      flatNo: j['flat_no'], wing: j['wing']);
  bool get active => status == 'active';
}

class Me {
  Me(this.user, this.memberships);
  final User user;
  final List<Membership> memberships;
  factory Me.fromJson(Json j) => Me(User.fromJson(j['user']), _list(j['memberships'], Membership.fromJson));
}

class Society {
  Society({
    required this.id, required this.name, required this.city, this.address, this.upiId, this.upiName, this.logoUrl,
    required this.status, required this.myRole, this.inviteCode, this.warnings = const [],
  });
  final String id, name, city, status;
  final String? address, upiId, upiName, logoUrl, inviteCode;
  final Role myRole;
  final List<String> warnings;
  factory Society.fromJson(Json j) => Society(
      id: j['id'], name: j['name'], city: j['city'], address: j['address'], upiId: j['upi_id'], upiName: j['upi_name'],
      logoUrl: j['logo_url'], status: j['status'], myRole: roleFrom(j['my_role']), inviteCode: j['invite_code'],
      warnings: ((j['warnings'] ?? const []) as List).cast<String>());
}

class Invite {
  Invite({required this.code, required this.deepLink, required this.webLink, required this.shareText});
  final String code, deepLink, webLink, shareText;
  factory Invite.fromJson(Json j) =>
      Invite(code: j['code'], deepLink: j['deep_link'], webLink: j['web_link'], shareText: j['share_text']);
}

class Member {
  Member({required this.id, required this.userId, this.name, required this.phone, required this.role, required this.status, this.flatNo, this.wing});
  final String id, userId, phone, status;
  final String? name, flatNo, wing;
  final Role role;
  factory Member.fromJson(Json j) => Member(
      id: j['id'], userId: j['user_id'], name: j['name'], phone: j['phone'], role: roleFrom(j['role']), status: j['status'],
      flatNo: j['flat_no'], wing: j['wing']);
  String get display => name ?? phone;
}

class EventDay {
  EventDay(this.id, this.date, this.label);
  final String id, date;
  final String? label;
  factory EventDay.fromJson(Json j) => EventDay(j['id'], j['date'], j['label']);
}

class Tier {
  Tier({
    required this.id, required this.name, this.description, required this.price, required this.capacity,
    required this.perUserLimit, required this.validDays, required this.dayIds, required this.allowGuests,
    required this.sold, required this.pending, required this.remaining,
  });
  final String id, name, validDays;
  final String? description;
  final int price, capacity, perUserLimit, sold, pending, remaining;
  final List<String> dayIds;
  final bool allowGuests;
  factory Tier.fromJson(Json j) => Tier(
      id: j['id'], name: j['name'], description: j['description'], price: _i(j['price']), capacity: _i(j['capacity']),
      perUserLimit: _i(j['per_user_limit']), validDays: j['valid_days'], dayIds: ((j['day_ids'] ?? const []) as List).cast<String>(),
      allowGuests: j['allow_guests'], sold: _i(j['sold']), pending: _i(j['pending']), remaining: _i(j['remaining']));
}

class EventT {
  EventT({
    required this.id, required this.societyId, required this.title, this.description, this.venue, required this.startsAt,
    required this.endsAt, this.bannerUrl, this.bookingDeadline, required this.status, required this.isPaid,
    required this.days, required this.tiers, required this.bookingOpen, required this.isOver,
  });
  final String id, societyId, title, status;
  final String? description, venue, bannerUrl;
  final DateTime startsAt, endsAt;
  final DateTime? bookingDeadline;
  final bool isPaid, bookingOpen, isOver;
  final List<EventDay> days;
  final List<Tier> tiers;
  factory EventT.fromJson(Json j) => EventT(
      id: j['id'], societyId: j['society_id'], title: j['title'], description: j['description'], venue: j['venue'],
      startsAt: _dt(j['starts_at']), endsAt: _dt(j['ends_at']), bannerUrl: j['banner_url'], bookingDeadline: _dtn(j['booking_deadline']),
      status: j['status'], isPaid: j['is_paid'], days: _list(j['days'], EventDay.fromJson), tiers: _list(j['tiers'], Tier.fromJson),
      bookingOpen: j['booking_open'], isOver: j['is_over']);

  /// Cheapest tier that still has seats, or null when sold out.
  int? get minPrice {
    final p = tiers.where((t) => t.remaining > 0).map((t) => t.price);
    return p.isEmpty ? null : p.reduce((a, b) => a < b ? a : b);
  }

  bool get soldOut => tiers.isNotEmpty && minPrice == null;
  String dayDate(String dayId) => days.firstWhere((d) => d.id == dayId, orElse: () => EventDay('', '', null)).date;
}

class Volunteer {
  Volunteer(this.userId, this.name, this.phone, this.expiresAt, this.active);
  final String userId, phone;
  final String? name;
  final DateTime expiresAt;
  final bool active;
  factory Volunteer.fromJson(Json j) => Volunteer(j['user_id'], j['name'], j['phone'], _dt(j['expires_at']), j['active']);
}

class Holder {
  Holder({this.name = '', this.type = 'member'});
  String name, type;
  factory Holder.fromJson(Json j) => Holder(name: j['name'], type: j['type']);
  Json toJson() => {'name': name.trim(), 'type': type};
}

class PaymentInstructions {
  PaymentInstructions({required this.amount, this.upiId, this.payeeName, this.note, this.upiUri});
  final int amount;
  final String? upiId, payeeName, note, upiUri;
  factory PaymentInstructions.fromJson(Json j) => PaymentInstructions(
      amount: _i(j['amount']), upiId: j['upi_id'], payeeName: j['payee_name'], note: j['note'], upiUri: j['upi_uri']);
}

class OrderItem {
  OrderItem({required this.tierId, required this.tierName, required this.qty, required this.unitPrice, required this.holders});
  final String tierId, tierName;
  final int qty, unitPrice;
  final List<Holder> holders;
  factory OrderItem.fromJson(Json j) => OrderItem(
      tierId: j['tier_id'], tierName: j['tier_name'], qty: _i(j['qty']), unitPrice: _i(j['unit_price']), holders: _list(j['holders'], Holder.fromJson));
}

class OrderMember {
  OrderMember(this.userId, this.name, this.phone, this.wing, this.flatNo);
  final String userId, phone;
  final String? name, wing, flatNo;
  factory OrderMember.fromJson(Json j) => OrderMember(j['user_id'], j['name'], j['phone'], j['wing'], j['flat_no']);
  String get display => name ?? phone;
  String get flat => [wing, flatNo].whereType<String>().where((s) => s.isNotEmpty).join('-');
}

class Order {
  Order({
    required this.id, required this.refCode, required this.eventId, required this.eventTitle, required this.status,
    required this.totalAmount, this.paidAmount, this.utr, required this.hasScreenshot, this.screenshotUrl,
    this.paymentSubmittedAt, required this.flags, this.rejectReason, required this.createdAt, this.expiresAt,
    required this.items, this.payment, this.member,
  });
  final String id, refCode, eventId, eventTitle, status;
  final int totalAmount;
  final int? paidAmount;
  final String? utr, screenshotUrl, rejectReason;
  final bool hasScreenshot;
  final DateTime? paymentSubmittedAt, expiresAt;
  final DateTime createdAt;
  final List<String> flags;
  final List<OrderItem> items;
  final PaymentInstructions? payment;
  final OrderMember? member;
  factory Order.fromJson(Json j) => Order(
      id: j['id'], refCode: j['ref_code'], eventId: j['event_id'], eventTitle: j['event_title'], status: j['status'],
      totalAmount: _i(j['total_amount']), paidAmount: _in(j['paid_amount']), utr: j['utr'], hasScreenshot: j['has_screenshot'],
      screenshotUrl: j['screenshot_url'], paymentSubmittedAt: _dtn(j['payment_submitted_at']),
      flags: ((j['flags'] ?? const []) as List).cast<String>(), rejectReason: j['reject_reason'], createdAt: _dt(j['created_at']),
      expiresAt: _dtn(j['expires_at']), items: _list(j['items'], OrderItem.fromJson),
      payment: j['payment'] == null ? null : PaymentInstructions.fromJson(j['payment']),
      member: j['member'] == null ? null : OrderMember.fromJson(j['member']));
  bool get submitted => paymentSubmittedAt != null;
  bool get pending => status == 'pending';
}

class OrderSummary {
  OrderSummary(this.pending, this.pendingFlagged, this.awaitingPayment);
  final int pending, pendingFlagged, awaitingPayment;
  factory OrderSummary.fromJson(Json j) => OrderSummary(_i(j['pending']), _i(j['pending_flagged']), _i(j['awaiting_payment']));
}

class PassEvent {
  PassEvent({required this.id, required this.societyId, required this.societyName, required this.title, this.venue, required this.startsAt, required this.endsAt, this.bannerUrl});
  final String id, societyId, societyName, title;
  final String? venue, bannerUrl;
  final DateTime startsAt, endsAt;
  factory PassEvent.fromJson(Json j) => PassEvent(
      id: j['id'], societyId: j['society_id'], societyName: j['society_name'], title: j['title'], venue: j['venue'],
      startsAt: _dt(j['starts_at']), endsAt: _dt(j['ends_at']), bannerUrl: j['banner_url']);
}

class PassT {
  PassT({
    required this.id, required this.orderId, required this.event, required this.tierName, required this.holderName,
    required this.holderType, required this.qrToken, required this.status, required this.validDays, required this.validDates,
    required this.scannedDates, required this.raw,
  });
  final String id, orderId, tierName, holderName, holderType, qrToken, status, validDays;
  final PassEvent event;
  final List<String> validDates, scannedDates;
  final Json raw; // original JSON → written to the offline cache
  factory PassT.fromJson(Json j) => PassT(
      id: j['id'], orderId: j['order_id'], event: PassEvent.fromJson(j['event']), tierName: j['tier_name'],
      holderName: j['holder_name'], holderType: j['holder_type'], qrToken: j['qr_token'], status: j['status'],
      validDays: j['valid_days'], validDates: ((j['valid_dates'] ?? const []) as List).cast<String>(),
      scannedDates: ((j['scanned_dates'] ?? const []) as List).cast<String>(), raw: j);
  bool get revoked => status == 'revoked';
}

class Counters {
  Counters(this.sold, this.scannedToday, this.expectedToday);
  final int sold, scannedToday, expectedToday;
  factory Counters.fromJson(Json j) => Counters(_i(j['sold']), _i(j['scanned_today']), _i(j['expected_today']));
}

class ScanResult {
  ScanResult({required this.ok, required this.result, required this.message, this.holderName, this.holderType, this.tierName, this.scannedAt, this.scannedBy, required this.counters});
  final bool ok;
  final String result, message;
  final String? holderName, holderType, tierName, scannedBy;
  final DateTime? scannedAt;
  final Counters counters;
  factory ScanResult.fromJson(Json j) => ScanResult(
      ok: j['ok'], result: j['result'], message: j['message'], holderName: j['holder_name'], holderType: j['holder_type'],
      tierName: j['tier_name'], scannedAt: _dtn(j['scanned_at']), scannedBy: j['scanned_by'], counters: Counters.fromJson(j['counters']));
}

class ScanEvent {
  ScanEvent(this.eventId, this.title, this.venue, this.day, this.counters);
  final String eventId, title;
  final String? venue, day;
  final Counters counters;
  factory ScanEvent.fromJson(Json j) => ScanEvent(j['event_id'], j['title'], j['venue'], j['day'], Counters.fromJson(j['counters']));
}

class Report {
  Report({required this.eventId, required this.title, required this.totals, required this.byTier, required this.byWing, required this.byDay});
  final String eventId, title;
  final Json totals;
  final List<Json> byTier, byWing, byDay;
  factory Report.fromJson(Json j) => Report(
      eventId: j['event_id'], title: j['title'], totals: j['totals'], byTier: (j['by_tier'] as List).cast<Json>(),
      byWing: (j['by_wing'] as List).cast<Json>(), byDay: (j['by_day'] as List).cast<Json>());
  int total(String k) => _i(totals[k]);
}

class GalleryItem {
  GalleryItem({required this.id, this.eventId, required this.url, required this.thumbUrl, required this.status, this.uploaderName, required this.mine, required this.createdAt});
  final String id, url, thumbUrl, status;
  final String? eventId, uploaderName;
  final bool mine;
  final DateTime createdAt;
  factory GalleryItem.fromJson(Json j) => GalleryItem(
      id: j['id'], eventId: j['event_id'], url: j['url'], thumbUrl: j['thumb_url'], status: j['status'],
      uploaderName: (j['uploaded_by'] as Json)['name'], mine: j['mine'], createdAt: _dt(j['created_at']));
}

class Presign {
  Presign(this.uploadId, this.url, this.method, this.headers);
  final String uploadId, url, method;
  final Map<String, String> headers;
  factory Presign.fromJson(Json j) =>
      Presign(j['upload_id'], j['upload_url'], j['method'], (j['headers'] as Map).map((k, v) => MapEntry('$k', '$v')));
}
