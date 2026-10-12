import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { api, type AuditRow, type Page } from '../api';
import { ACTION_LABELS, formatDateTime } from '../format';
import { Badge, Card, Empty, ErrorBox, Pagination, Spinner, Td, Th } from '../components/ui';

const LIMIT = 30;

export default function Audit() {
  const [params, setParams] = useSearchParams();
  const societyId = params.get('society_id') ?? '';
  const [action, setAction] = useState('');
  const [offset, setOffset] = useState(0);
  const q = useQuery({ queryKey: ['audit', societyId, action, offset], queryFn: () => api<Page<AuditRow>>('/admin/audit-logs', { query: { society_id: societyId, action, limit: LIMIT, offset } }) });
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Audit logs</h1>
        <div className="flex gap-2">
          {societyId && <button onClick={() => setParams({})} className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50">Clear society filter ✕</button>}
          <select value={action} onChange={(e) => { setAction(e.target.value); setOffset(0); }} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" aria-label="Action filter">
            <option value="">All actions</option><option value="order.">Orders</option><option value="member.">Members</option><option value="society.">Society</option>
            <option value="event.">Events</option><option value="pass.">Passes</option><option value="gallery.">Gallery</option><option value="report.">Exports</option>
          </select>
        </div>
      </div>
      <Card className="overflow-x-auto">
        {q.isLoading ? <Spinner /> : q.isError ? <ErrorBox error={q.error} onRetry={q.refetch} /> : !q.data?.items.length ? <Empty>No audit entries.</Empty> : (
          <>
            <table className="min-w-full divide-y divide-slate-100">
              <thead className="bg-slate-50"><tr><Th>When</Th><Th>Society</Th><Th>Actor</Th><Th>Action</Th><Th>Details</Th></tr></thead>
              <tbody className="divide-y divide-slate-100 align-top">
                {q.data.items.map((a) => (
                  <tr key={a.id}>
                    <Td className="whitespace-nowrap text-slate-500">{formatDateTime(a.created_at)}</Td>
                    <Td>{a.society_name ?? '—'}</Td>
                    <Td>{a.actor_name ?? (a.actor_id ? a.actor_phone : <span className="text-slate-400">system</span>)}<div className="text-xs text-slate-500">{a.actor_name && a.actor_phone}</div></Td>
                    <Td><Badge tone={a.action.includes('reject') || a.action.includes('suspend') || a.action.includes('delete') || a.action.includes('remove') ? 'red' : a.action.includes('approve') ? 'green' : 'indigo'}>{ACTION_LABELS[a.action] ?? a.action}</Badge></Td>
                    <Td className="max-w-md font-mono text-xs text-slate-600">{a.entity}{a.entity_id ? ` ${a.entity_id.slice(0, 8)}…` : ''}{Object.keys(a.meta).length > 0 && <div className="mt-1 break-words text-slate-500">{JSON.stringify(a.meta)}</div>}</Td>
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
