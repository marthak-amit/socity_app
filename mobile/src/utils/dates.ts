const pad = (n: number) => String(n).padStart(2, '0');

export function formatTime(iso: string, locale?: string): string {
  return new Date(iso).toLocaleTimeString(locale, { hour: 'numeric', minute: '2-digit' });
}

export function formatDate(iso: string, locale?: string): string {
  return new Date(iso).toLocaleDateString(locale, { day: 'numeric', month: 'short', year: 'numeric' });
}

export function formatDateTime(iso: string, locale?: string): string {
  return `${formatDate(iso, locale)}, ${formatTime(iso, locale)}`;
}

/** "12 Oct" or "12 – 20 Oct" for multi-day events. */
export function formatDateRange(startIso: string, endIso: string, locale?: string): string {
  const s = new Date(startIso);
  const e = new Date(endIso);
  const short = (d: Date) => d.toLocaleDateString(locale, { day: 'numeric', month: 'short' });
  if (s.toDateString() === e.toDateString()) return short(s);
  if (s.getMonth() === e.getMonth() && s.getFullYear() === e.getFullYear()) {
    return `${s.getDate()} – ${short(e)}`;
  }
  return `${short(s)} – ${short(e)}`;
}

/** A plain YYYY-MM-DD string from the API → local Date at noon (avoids timezone day-shift). */
export function parseDay(day: string): Date {
  const [y, m, d] = day.split('-').map(Number);
  return new Date(y, m - 1, d, 12);
}

export function formatDay(day: string, locale?: string): string {
  return parseDay(day).toLocaleDateString(locale, { weekday: 'short', day: 'numeric', month: 'short' });
}

export function toDayString(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Whole minutes → "1h 05m" / "23m" / "expired" — for the order expiry countdown. */
export function formatCountdown(targetIso: string, now: number = Date.now()): string {
  const ms = new Date(targetIso).getTime() - now;
  if (ms <= 0) return 'expired';
  const mins = Math.floor(ms / 60000);
  const h = Math.floor(mins / 60);
  if (h >= 48) return `${Math.floor(h / 24)}d`;
  if (h >= 1) return `${h}h ${pad(mins % 60)}m`;
  return `${mins}m`;
}
