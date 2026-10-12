const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? 'http://localhost:8000/api/v1';

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

export type User = { id: string; phone: string; name: string | null; is_super_admin: boolean };
export type Page<T> = { items: T[]; total: number; limit: number; offset: number };
type Tokens = { access_token: string; refresh_token: string; user: User };

const KEY = 'sp_admin_session';
export const session = {
  get(): Tokens | null {
    try { return JSON.parse(localStorage.getItem(KEY) ?? 'null'); } catch { return null; }
  },
  set(t: Tokens | null) {
    if (t) localStorage.setItem(KEY, JSON.stringify(t)); else localStorage.removeItem(KEY);
    window.dispatchEvent(new Event('sp-session'));
  },
};

let refreshing: Promise<boolean> | null = null;
async function refresh(): Promise<boolean> {
  const s = session.get();
  if (!s) return false;
  const res = await fetch(`${BASE}/auth/refresh`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: s.refresh_token }) });
  if (!res.ok) { session.set(null); return false; }
  session.set(await res.json());
  return true;
}

export async function api<T>(path: string, init: { method?: string; body?: unknown; query?: Record<string, string | number | undefined | null>; auth?: boolean } = {}): Promise<T> {
  const q = Object.entries(init.query ?? {}).filter(([, v]) => v !== undefined && v !== null && v !== '').map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`).join('&');
  const send = () => fetch(`${BASE}${path}${q ? `?${q}` : ''}`, {
    method: init.method ?? 'GET',
    headers: { 'Content-Type': 'application/json', ...(init.auth !== false && session.get() ? { Authorization: `Bearer ${session.get()!.access_token}` } : {}) },
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
  });
  let res = await send();
  if (res.status === 401 && init.auth !== false) {
    refreshing ??= refresh().finally(() => (refreshing = null));
    if (await refreshing) res = await send();
  }
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) {
    const d = data?.detail;
    throw new ApiError(res.status, d?.code ?? 'http_error', d?.message ?? (typeof d === 'string' ? d : `Request failed (${res.status})`));
  }
  return data as T;
}

export type PlatformStats = {
  societies: Record<string, number>; users: number; active_members: number; events: Record<string, number>;
  orders: Record<string, number>; collected_amount: number; flagged_pending_orders: number; passes: number; scans: number;
};
export type AdminSociety = {
  id: string; name: string; city: string; status: string; logo_url: string | null; created_at: string; members: number; admins: number;
  events: number; collected_amount: number; owner_name: string | null; owner_phone: string | null;
};
export type FlaggedOrder = {
  id: string; ref_code: string; society_id: string; society_name: string; event_title: string; status: string; total_amount: number;
  paid_amount: number | null; utr: string | null; flags: string[]; buyer_name: string | null; buyer_phone: string; created_at: string;
};
export type AuditRow = {
  id: number; created_at: string; society_id: string | null; society_name: string | null; actor_id: string | null; actor_name: string | null;
  actor_phone: string | null; action: string; entity: string; entity_id: string | null; meta: Record<string, unknown>;
};
