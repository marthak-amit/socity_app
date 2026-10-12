import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api, type AdminSociety, type Page } from '../api';
import { formatDateTime, formatINR } from '../format';
import { Badge, Button, Card, Empty, ErrorBox, Modal, Pagination, Spinner, Td, Th } from '../components/ui';

const LIMIT = 20;

export default function Societies() {
  const qc = useQueryClient();
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');
  const [offset, setOffset] = useState(0);
  const [target, setTarget] = useState<AdminSociety | null>(null);
  const [reason, setReason] = useState('');
  const list = useQuery({
    queryKey: ['societies', q, status, offset],
    queryFn: () => api<Page<AdminSociety>>('/admin/societies', { query: { q, status, limit: LIMIT, offset } }),
  });
  const toggle = useMutation({
    mutationFn: (s: AdminSociety) =>
      s.status === 'suspended'
        ? api(`/admin/societies/${s.id}/unsuspend`, { method: 'POST' })
        : api(`/admin/societies/${s.id}/suspend`, { method: 'POST', body: { reason } }),
    onSuccess: () => { setTarget(null); setReason(''); void qc.invalidateQueries({ queryKey: ['societies'] }); void qc.invalidateQueries({ queryKey: ['stats'] }); },
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Societies</h1>
        <div className="flex gap-2">
          <input value={q} onChange={(e) => { setQ(e.target.value); setOffset(0); }} placeholder="Search name or city…" className="w-56 rounded-lg border border-slate-300 px-3 py-2 text-sm" />
          <select value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }} className="rounded-lg border border-slate-300 px-3 py-2 text-sm" aria-label="Status filter">
            <option value="">All statuses</option><option value="active">Active</option><option value="suspended">Suspended</option><option value="deleted">Deleted</option>
          </select>
        </div>
      </div>
      <Card className="overflow-x-auto">
        {list.isLoading ? <Spinner /> : list.isError ? <ErrorBox error={list.error} onRetry={list.refetch} /> : !list.data?.items.length ? <Empty>No societies found.</Empty> : (
          <>
            <table className="min-w-full divide-y divide-slate-100">
              <thead className="bg-slate-50"><tr><Th>Society</Th><Th>Owner</Th><Th>Members</Th><Th>Events</Th><Th>Collected</Th><Th>Status</Th><Th>Created</Th><Th /></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {list.data.items.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50">
                    <Td><div className="font-medium">{s.name}</div><div className="text-xs text-slate-500">{s.city}</div></Td>
                    <Td><div>{s.owner_name ?? '—'}</div><div className="text-xs text-slate-500">{s.owner_phone}</div></Td>
                    <Td>{s.members} <span className="text-xs text-slate-400">({s.admins} admin{s.admins === 1 ? '' : 's'})</span>{s.admins < 2 && s.status === 'active' && <span title="Fewer than 2 admins"> ⚠️</span>}</Td>
                    <Td>{s.events}</Td>
                    <Td>{formatINR(s.collected_amount)}</Td>
                    <Td><Badge tone={s.status === 'active' ? 'green' : s.status === 'suspended' ? 'red' : 'gray'}>{s.status}</Badge></Td>
                    <Td className="whitespace-nowrap text-slate-500">{formatDateTime(s.created_at)}</Td>
                    <Td className="whitespace-nowrap text-right">
                      <Link to={`/audit?society_id=${s.id}`} className="mr-3 text-xs font-medium text-brand-700 hover:underline">Audit</Link>
                      {s.status !== 'deleted' && (
                        <Button variant={s.status === 'suspended' ? 'secondary' : 'danger'} onClick={() => { setTarget(s); setReason(''); }}>
                          {s.status === 'suspended' ? 'Reinstate' : 'Suspend'}
                        </Button>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination total={list.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        )}
      </Card>
      {target && (
        <Modal title={target.status === 'suspended' ? `Reinstate ${target.name}?` : `Suspend ${target.name}?`} onClose={() => setTarget(null)}>
          {target.status === 'suspended' ? (
            <p className="text-sm text-slate-600">Members and admins will regain access immediately.</p>
          ) : (
            <>
              <p className="mb-3 text-sm text-slate-600">All members and admins are locked out of this society (events, passes, scanning) until it is reinstated. Society admins are notified with your reason.</p>
              <label className="block text-sm font-medium">Reason
                <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" placeholder="e.g. Fraud complaint #123" />
              </label>
            </>
          )}
          {toggle.isError && <p role="alert" className="mt-3 rounded bg-red-50 p-2 text-sm text-red-700">{(toggle.error as Error).message}</p>}
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setTarget(null)}>Cancel</Button>
            <Button variant={target.status === 'suspended' ? 'primary' : 'danger'} disabled={toggle.isPending || (target.status !== 'suspended' && reason.trim().length < 3)} onClick={() => toggle.mutate(target)}>
              {toggle.isPending ? 'Working…' : target.status === 'suspended' ? 'Reinstate' : 'Suspend'}
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
