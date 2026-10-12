import Constants from 'expo-constants';
import { useAuth } from '@/store/auth';

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public extra: Record<string, unknown> = {}) {
    super(message);
  }
}

/** API base URL: EXPO_PUBLIC_API_URL, else the machine running the Expo packager (works for phones on the same Wi-Fi). */
export function apiBase(): string {
  const fromEnv = process.env.EXPO_PUBLIC_API_URL;
  if (fromEnv) return fromEnv.replace(/\/$/, '');
  const host = (Constants.expoConfig?.hostUri ?? '').split(':')[0];
  return `http://${host || 'localhost'}:8000/api/v1`;
}

type Opts = { method?: string; body?: unknown; query?: Record<string, string | number | boolean | undefined | null>; auth?: boolean };

let refreshing: Promise<boolean> | null = null;

async function refreshTokens(): Promise<boolean> {
  const { refreshToken, setSession, logout } = useAuth.getState();
  if (!refreshToken) return false;
  try {
    const res = await fetch(`${apiBase()}/auth/refresh`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) {
      if (res.status === 401) await logout(); // refresh token rejected → signed out for real
      return false;
    }
    const data = await res.json();
    await setSession(data.access_token, data.refresh_token, data.user);
    return true;
  } catch {
    return false; // offline: keep the session, just fail this request
  }
}

function qs(query?: Opts['query']): string {
  if (!query) return '';
  const p = Object.entries(query).filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return p.length ? `?${p.join('&')}` : '';
}

export async function api<T>(path: string, opts: Opts = {}): Promise<T> {
  const { auth = true } = opts;
  const send = async () => {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
    const token = useAuth.getState().accessToken;
    if (auth && token) headers.Authorization = `Bearer ${token}`;
    return fetch(`${apiBase()}${path}${qs(opts.query)}`, {
      method: opts.method ?? 'GET', headers, body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  };
  let res: Response;
  try {
    res = await send();
  } catch {
    throw new ApiError(0, 'network_error', 'No connection. Check your internet and try again.');
  }
  if (res.status === 401 && auth) {
    refreshing ??= refreshTokens().finally(() => (refreshing = null));
    if (await refreshing) res = await send();
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const data = text ? safeJson(text) : null;
  if (!res.ok) {
    const d = data?.detail;
    if (d && typeof d === 'object' && 'code' in d) throw new ApiError(res.status, d.code, d.message ?? d.code, d);
    throw new ApiError(res.status, 'http_error', typeof d === 'string' ? d : `Request failed (${res.status})`);
  }
  return data as T;
}

function safeJson(text: string) {
  try { return JSON.parse(text); } catch { return null; }
}

export const get = <T,>(path: string, query?: Opts['query']) => api<T>(path, { query });
export const post = <T,>(path: string, body?: unknown) => api<T>(path, { method: 'POST', body: body ?? {} });
export const patch = <T,>(path: string, body?: unknown) => api<T>(path, { method: 'PATCH', body });
export const del = <T,>(path: string, body?: unknown) => api<T>(path, { method: 'DELETE', body });

/** Presign → PUT bytes → returns the upload id to hand to the endpoint that uses the file. */
export async function uploadImage(
  societyId: string | null, purpose: 'screenshot' | 'gallery' | 'banner' | 'logo' | 'avatar', uri: string, mime?: string | null,
): Promise<string> {
  const blob = await (await fetch(uri)).blob();
  const contentType = mime && mime.startsWith('image/') ? mime : blob.type && blob.type.startsWith('image/') ? blob.type : 'image/jpeg';
  const presign = await post<import('./types').Presign>(
    purpose === 'avatar' ? '/me/avatar-upload' : `/societies/${societyId}/uploads/presign`,
    { purpose, content_type: contentType, size: blob.size },
  );
  const put = await fetch(presign.upload_url, { method: presign.method, headers: presign.headers, body: blob });
  if (!put.ok) throw new ApiError(put.status, 'upload_failed', 'Photo upload failed. Please try again.');
  return presign.upload_id;
}

/** Download an authenticated file (CSV/XLSX export) into the cache and return its URI. */
export async function downloadExport(path: string, filename: string): Promise<string> {
  const { File, Paths } = await import('expo-file-system');
  const res = await fetch(`${apiBase()}${path}`, { headers: { Authorization: `Bearer ${useAuth.getState().accessToken}` } });
  if (!res.ok) throw new ApiError(res.status, 'export_failed', 'Export failed');
  const file = new File(Paths.cache, filename);
  if (file.exists) file.delete();
  file.create();
  file.write(new Uint8Array(await res.arrayBuffer()));
  return file.uri;
}
