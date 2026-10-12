import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, type FlaggedOrder, type Page } from '../api';
import { formatDateTime, formatINR } from '../format';
import { Badge, Card, Empty, ErrorBox, Pagination, Spinner, Td, Th } from '../components/ui';

const LIMIT = 25;
const FLAG: Record<string, string> = { duplicate_utr: 'Duplicate UTR', amount_mismatch: 'Amount mismatch', missing_utr: 'Missing UTR' };

export default function Flagged() {
  const [status, setStatus] = useState('pending');
  const [offset, setOffset] = useState(0);
  const q = useQuery({ queryKey: ['flagged', status, offset], queryFn: () => api<Page<FlaggedOrder>>('/admin/orders/flagged', { query: { status, limit: LIMIT, offset } }) });
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Flagged orders</h1>
          <p className="text-sm text-slate-500">Orders the system flagged for review. Payment screenshots are only visible to each society's own admins.</p>
        </div>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" aria-label="Order status">
          <option value="pending">Pending</option><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="cancelled">Cancelled</option>
        </select>
      </div>
      <Card className="overflow-x-auto">
        {q.isLoading ? <Spinner /> : q.isError ? <ErrorBox error={q.error} onRetry={q.refetch} /> : !q.data?.items.length ? <Empty>No flagged orders 🎉</Empty> : (
          <>
            <table className="min-w-full divide-y divide-slate-100">
              <thead className="bg-slate-50"><tr><Th>Order</Th><Th>Society / event</Th><Th>Buyer</Th><Th>Amount</Th><Th>UTR</Th><Th>Flags</Th><Th>Placed</Th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {q.data.items.map((o) => (
                  <tr key={o.id}>
                    <Td><div className="font-mono text-xs">{o.ref_code}</div><Badge tone={o.status === 'approved' ? 'green' : o.status === 'pending' ? 'amber' : 'gray'}>{o.status}</Badge></Td>
                    <Td><div className="font-medium">{o.society_name}</div><div className="text-xs text-slate-500">{o.event_title}</div></Td>
                    <Td><div>{o.buyer_name ?? '—'}</div><div className="text-xs text-slate-500">{o.buyer_phone}</div></Td>
                    <Td>{formatINR(o.total_amount)}{o.paid_amount !== null && o.paid_amount !== o.total_amount && <div className="text-xs text-red-600">claims {formatINR(o.paid_amount)}</div>}</Td>
                    <Td className="font-mono text-xs">{o.utr ?? '—'}</Td>
                    <Td><div className="flex flex-wrap gap-1">{o.flags.map((f) => <Badge key={f} tone="amber">{FLAG[f] ?? f}</Badge>)}</div></Td>
                    <Td className="whitespace-nowrap text-slate-500">{formatDateTime(o.created_at)}</Td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination total={q.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        )}
      </Card>
    </div>
  );
}
