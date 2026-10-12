/** ₹ with Indian digit grouping (12,34,567). */
export function formatINR(amount: number): string {
  const neg = amount < 0;
  const digits = Math.abs(Math.round(amount)).toString();
  const out = digits.length <= 3 ? digits : `${digits.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ',')},${digits.slice(-3)}`;
  return `${neg ? '-' : ''}₹${out}`;
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function timeAgo(iso: string, now: number = Date.now()): string {
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

/** Bare 10-digit Indian numbers get +91; anything starting with + is kept. */
export function normalizePhone(input: string): string {
  const t = input.replace(/[\s-]/g, '');
  return t.startsWith('+') ? t : `+91${t.replace(/^0/, '')}`;
}

export const ACTION_LABELS: Record<string, string> = {
  'order.approve': 'Order approved', 'order.reject': 'Order rejected', 'order.bulk_approve': 'Bulk approval', 'order.cancel': 'Order cancelled',
  'order.expire': 'Order expired', 'order.auto_approve': 'Free order issued', 'society.create': 'Society created', 'society.update': 'Society updated',
  'society.delete': 'Society deleted', 'society.suspend': 'Society suspended', 'society.unsuspend': 'Society reinstated',
  'member.role_change': 'Role changed', 'member.remove': 'Member removed', 'member.approve': 'Member approved', 'member.reject': 'Join rejected',
  'event.publish': 'Event published', 'event.cancel': 'Event cancelled', 'pass.revoke': 'Pass revoked', 'report.export': 'Report exported',
};
