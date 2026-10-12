import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api, type PlatformStats } from '../api';
import { formatINR } from '../format';
import { Card, ErrorBox, Spinner, Stat } from '../components/ui';

export default function Dashboard() {
  const q = useQuery({ queryKey: ['stats'], queryFn: () => api<PlatformStats>('/admin/stats'), refetchInterval: 30_000 });
  if (q.isLoading) return <Spinner />;
  if (q.isError || !q.data) return <ErrorBox error={q.error} onRetry={q.refetch} />;
  const s = q.data;
  const n = (m: Record<string, number>, k: string) => m[k] ?? 0;
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Platform overview</h1>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Societies" value={n(s.societies, 'active') + n(s.societies, 'suspended')} hint={`${n(s.societies, 'suspended')} suspended`} />
        <Stat label="Users" value={s.users} hint={`${s.active_members} active memberships`} />
        <Stat label="Collected" value={formatINR(s.collected_amount)} hint={`${n(s.orders, 'approved')} approved orders`} />
        <Stat label="Passes issued" value={s.passes} hint={`${s.scans} scans at the gate`} />
        <Stat label="Events live" value={n(s.events, 'published')} hint={`${n(s.events, 'draft')} drafts · ${n(s.events, 'closed')} closed`} />
        <Stat label="Pending orders" value={n(s.orders, 'pending')} hint={`${n(s.orders, 'rejected')} rejected · ${n(s.orders, 'cancelled')} cancelled`} />
        <Stat label="Flagged (pending)" value={s.flagged_pending_orders} tone={s.flagged_pending_orders ? 'danger' : undefined} hint="duplicate UTR / amount mismatch / missing UTR" />
      </div>
      {s.flagged_pending_orders > 0 && (
        <Card className="flex items-center justify-between border-amber-200 bg-amber-50 p-4 text-sm">
          <span>🚩 {s.flagged_pending_orders} pending order(s) have payment flags.</span>
          <Link to="/flagged" className="font-medium text-brand-700 hover:underline">Review →</Link>
        </Card>
      )}
    </div>
  );
}
