import type { Role } from '@/utils/roles';

export type Page<T> = { items: T[]; total: number; limit: number; offset: number };

export type User = {
  id: string; phone: string; name: string | null; avatar_url: string | null; locale: string; is_super_admin: boolean;
};
export type TokenPair = {
  access_token: string; refresh_token: string; expires_in: number; user: User; is_new_user: boolean;
};

export type SocietyBrief = { id: string; name: string; city: string; logo_url: string | null; status: string };
export type Membership = {
  id: string; society: SocietyBrief; role: Role; status: 'pending' | 'active' | 'removed'; flat_no: string | null; wing: string | null;
};
export type Me = { user: User; memberships: Membership[] };

export type Society = SocietyBrief & {
  address: string | null; upi_id: string | null; upi_name: string | null; timezone: string; created_at: string;
  my_role: Role; invite_code: string | null; warnings: string[];
};
export type Invite = { code: string; deep_link: string; web_link: string; share_text: string };

export type Member = {
  id: string; user_id: string; name: string | null; phone: string; role: Role; status: string;
  flat_no: string | null; wing: string | null; created_at: string;
};

export type EventDay = { id: string; date: string; label: string | null };
export type Tier = {
  id: string; name: string; description: string | null; price: number; capacity: number; per_user_limit: number;
  valid_days: 'all' | 'specific'; day_ids: string[]; allow_guests: boolean; sort_order: number;
  sold: number; pending: number; remaining: number;
};
export type EventStatus = 'draft' | 'published' | 'closed' | 'cancelled';
export type EventT = {
  id: string; society_id: string; title: string; description: string | null; venue: string | null;
  starts_at: string; ends_at: string; banner_url: string | null; booking_deadline: string | null;
  status: EventStatus; is_paid: boolean; payment_provider: string; days: EventDay[]; tiers: Tier[];
  booking_open: boolean; is_over: boolean; created_at: string;
};
export type Volunteer = { user_id: string; name: string | null; phone: string; expires_at: string; active: boolean };

export type OrderStatus = 'pending' | 'approved' | 'rejected' | 'cancelled';
export type OrderFlag = 'duplicate_utr' | 'amount_mismatch' | 'missing_utr';
export type Holder = { name: string; type: 'member' | 'guest' };
export type PaymentInstructions = {
  provider: string; amount: number; currency: string; upi_id: string | null; payee_name: string | null;
  note: string | null; upi_uri: string | null; requires_proof: boolean;
};
export type Order = {
  id: string; ref_code: string; event_id: string; event_title: string; society_id: string; status: OrderStatus;
  total_amount: number; paid_amount: number | null; utr: string | null; has_screenshot: boolean;
  screenshot_url: string | null; payment_submitted_at: string | null; flags: OrderFlag[]; reject_reason: string | null;
  reviewed_at: string | null; created_at: string; expires_at: string | null;
  items: { tier_id: string; tier_name: string; qty: number; unit_price: number; holders: Holder[] }[];
  payment: PaymentInstructions | null;
  member: { user_id: string; name: string | null; phone: string; wing: string | null; flat_no: string | null } | null;
};
export type OrderSummary = { pending: number; pending_flagged: number; awaiting_payment: number; approved: number; rejected: number };

export type PassT = {
  id: string; order_id: string; tier_id: string; tier_name: string; holder_name: string; holder_type: string;
  qr_token: string; status: 'active' | 'revoked'; valid_days: 'all' | 'specific'; valid_dates: string[];
  scanned_dates: string[]; created_at: string;
  event: {
    id: string; society_id: string; society_name: string; title: string; venue: string | null;
    starts_at: string; ends_at: string; banner_url: string | null;
  };
};

export type Counters = { sold: number; scanned_today: number; expected_today: number };
export type ScanResult = {
  ok: boolean; result: string; message: string; holder_name: string | null; holder_type: string | null;
  tier_name: string | null; pass_id: string | null; scanned_at: string | null; scanned_by: string | null;
  day: string | null; counters: Counters;
};
export type ScanEvent = {
  event_id: string; title: string; venue: string | null; starts_at: string; ends_at: string; day: string | null; counters: Counters;
};

export type Report = {
  event_id: string; title: string;
  totals: {
    collected_amount: number; pending_amount: number; pending_count: number; awaiting_payment_count: number;
    approved_orders: number; rejected_orders: number; passes_sold: number; passes_scanned: number;
  };
  by_tier: { tier_id: string; name: string; price: number; capacity: number; sold: number; pending: number; collected: number; scanned: number }[];
  by_wing: { wing: string; orders: number; passes: number; collected: number }[];
  by_day: { date: string; scanned: number; expected: number }[];
};

export type GalleryItem = {
  id: string; event_id: string | null; url: string; thumb_url: string; width: number | null; height: number | null;
  status: 'pending' | 'approved' | 'rejected'; uploaded_by: { id: string; name: string | null }; mine: boolean; created_at: string;
};

export type Presign = { upload_id: string; upload_url: string; method: string; headers: Record<string, string>; max_bytes: number };
