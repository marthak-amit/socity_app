/// Pure helpers (unit-tested): money, validation, deep links, dates, roles, UPI.
library;

// ------------------------------------------------------------------ money
/// 1500 → ₹1,500; 1234567 → ₹12,34,567 (Indian digit grouping).
String formatInr(num amount) {
  final neg = amount < 0;
  final digits = amount.abs().round().toString();
  String out;
  if (digits.length <= 3) {
    out = digits;
  } else {
    final last3 = digits.substring(digits.length - 3);
    var rest = digits.substring(0, digits.length - 3);
    final buf = StringBuffer();
    for (var i = 0; i < rest.length; i++) {
      if (i > 0 && (rest.length - i) % 2 == 0) buf.write(',');
      buf.write(rest[i]);
    }
    rest = buf.toString();
    out = '$rest,$last3';
  }
  return '${neg ? '-' : ''}₹$out';
}

String priceLabel(num price, {String free = 'Free'}) => price == 0 ? free : formatInr(price);

// ------------------------------------------------------------------ validation
/// Typed text → 10-digit Indian mobile, or null when invalid.
String? normalizeIndianPhone(String input) {
  final digits = input.replaceAll(RegExp(r'[^\d]'), '');
  String local = digits;
  if (digits.length == 12 && digits.startsWith('91')) {
    local = digits.substring(2);
  } else if (digits.length == 11 && digits.startsWith('0')) {
    local = digits.substring(1);
  }
  return RegExp(r'^[6-9]\d{9}$').hasMatch(local) ? local : null;
}

const utrLength = 12;
String sanitizeUtr(String input) {
  final d = input.replaceAll(RegExp(r'\D'), '');
  return d.length > utrLength ? d.substring(0, utrLength) : d;
}

bool isValidUtr(String input) => RegExp(r'^\d{12}$').hasMatch(input.replaceAll(RegExp(r'\s+'), ''));
bool isValidUpiId(String v) => RegExp(r'^[A-Za-z0-9.\-_]{1,64}@[A-Za-z][A-Za-z0-9]{1,31}$').hasMatch(v.trim());
bool isValidOtp(String v) => RegExp(r'^\d{6}$').hasMatch(v);

// ------------------------------------------------------------------ deep links
/// Invite code from `societypass://join?code=X`, `https://…/join/X`, or a bare code.
String? parseInviteCode(String input) {
  final text = input.trim();
  if (text.isEmpty) return null;
  final q = RegExp(r'[?&]code=([A-Za-z0-9]+)').firstMatch(text);
  if (q != null) return q.group(1)!.toUpperCase();
  final p = RegExp(r'/join/([A-Za-z0-9]+)').firstMatch(text);
  if (p != null) return p.group(1)!.toUpperCase();
  if (RegExp(r'^[A-Za-z0-9]{4,12}$').hasMatch(text)) return text.toUpperCase();
  return null;
}

// ------------------------------------------------------------------ UPI
String buildUpiUri({required String pa, required String pn, required num am, required String tn}) {
  final q = {'pa': pa, 'pn': pn, 'am': am.toStringAsFixed(2), 'cu': 'INR', 'tn': tn}
      .entries
      .map((e) => '${e.key}=${Uri.encodeComponent(e.value)}')
      .join('&');
  return 'upi://pay?$q';
}

// ------------------------------------------------------------------ roles
enum Role { member, volunteer, admin, owner }

Role roleFrom(String s) => Role.values.firstWhere((r) => r.name == s, orElse: () => Role.member);

bool atLeast(Role? role, Role min) => role != null && role.index >= min.index;
bool isAdminRole(Role? r) => atLeast(r, Role.admin);
bool canScan(Role? r) => atLeast(r, Role.volunteer);

enum TabKey { events, passes, gallery, scan, manage }

/// Bottom tabs per role (UX only — the server enforces the same rules).
List<TabKey> tabsForRole(Role? role) => [
      TabKey.events,
      TabKey.passes,
      TabKey.gallery,
      if (canScan(role)) TabKey.scan,
      if (isAdminRole(role)) TabKey.manage,
    ];

/// Roles `actor` may assign to `target` (mirrors the server rules).
List<Role> assignableRoles(Role? actor, Role target) {
  if (target == Role.owner) return const [];
  if (actor == Role.owner) return [Role.admin, Role.volunteer, Role.member].where((r) => r != target).toList();
  if (actor == Role.admin && (target == Role.member || target == Role.volunteer)) {
    return [Role.volunteer, Role.member].where((r) => r != target).toList();
  }
  return const [];
}

// ------------------------------------------------------------------ dates
String two(int n) => n.toString().padLeft(2, '0');

const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const _weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

/// Plain `YYYY-MM-DD` from the API → local noon DateTime (no timezone day-shift).
DateTime parseDay(String day) {
  final p = day.split('-').map(int.parse).toList();
  return DateTime(p[0], p[1], p[2], 12);
}

String toDayString(DateTime d) => '${d.year}-${two(d.month)}-${two(d.day)}';
String formatDay(String day) {
  final d = parseDay(day);
  return '${_weekdays[d.weekday - 1]}, ${d.day} ${_months[d.month - 1]}';
}

String formatDate(DateTime d) => '${d.day} ${_months[d.month - 1]} ${d.year}';
String formatTime(DateTime d) {
  final h = d.hour % 12 == 0 ? 12 : d.hour % 12;
  return '$h:${two(d.minute)} ${d.hour < 12 ? 'AM' : 'PM'}';
}

String formatDateTime(DateTime d) => '${formatDate(d)}, ${formatTime(d)}';

/// "12 Oct" or "12 – 20 Oct" for multi-day events.
String formatDateRange(DateTime s, DateTime e) {
  String short(DateTime d) => '${d.day} ${_months[d.month - 1]}';
  if (s.year == e.year && s.month == e.month && s.day == e.day) return short(s);
  if (s.year == e.year && s.month == e.month) return '${s.day} – ${short(e)}';
  return '${short(s)} – ${short(e)}';
}

/// Order-expiry countdown: "23m", "5h 05m", "expired".
String formatCountdown(DateTime target, {DateTime? now}) {
  final diff = target.difference(now ?? DateTime.now());
  if (diff.isNegative || diff.inSeconds == 0) return 'expired';
  final mins = diff.inMinutes;
  final h = mins ~/ 60;
  if (h >= 48) return '${h ~/ 24}d';
  if (h >= 1) return '${h}h ${two(mins % 60)}m';
  return '${mins}m';
}
