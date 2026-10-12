import React, { useState } from 'react';
import { FlatList, RefreshControl, View } from 'react-native';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { post } from '@/api/client';
import type { Order, OrderFlag } from '@/api/types';
import { Badge, Button, Card, EmptyState, ErrorState, Ionicons, LoadingView, Row, SegmentedControl, T, confirm, errorMessage, toast } from '@/components/ui';
import { flat, useApprovalQueue, useOrderSummary } from '@/hooks/queries';
import { useActiveSociety } from '@/hooks/useSociety';
import { colors, space } from '@/theme';
import { formatDateTime } from '@/utils/dates';
import { formatINR } from '@/utils/money';

type Tab = 'pending' | 'approved' | 'rejected';

export function FlagBadges({ flags }: { flags: OrderFlag[] }) {
  const { t } = useTranslation();
  return <>{flags.map((f) => <Badge key={f} tone="warning" icon="flag" text={t(`approvals.flag.${f}`)} />)}</>;
}

export default function Approvals() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const { societyId } = useActiveSociety();
  const [tab, setTab] = useState<Tab>('pending');
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const q = useApprovalQueue(societyId, tab);
  const summary = useOrderSummary(societyId);
  const orders = flat(q.data);

  const toggle = (o: Order) => {
    if (o.status !== 'pending') return;
    setSelected((prev) => { const n = new Set(prev); if (n.has(o.id)) n.delete(o.id); else n.add(o.id); return n; });
  };

  const bulk = async () => {
    if (!(await confirm(t('approvals.bulkApprove', { n: selected.size }), t('approvals.approveConfirm'), t('common.approve')))) return;
    setBusy(true);
    try {
      const r = await post<{ approved: string[]; skipped: unknown[] }>(`/societies/${societyId}/orders/bulk-approve`, { order_ids: [...selected] });
      toast(`${t('approvals.approvedN', { n: r.approved.length })}${r.skipped.length ? ` · ${t('approvals.skipped', { n: r.skipped.length })}` : ''}`, r.skipped.length ? 'neutral' : 'success');
      setSelected(new Set());
      await Promise.all([qc.invalidateQueries({ queryKey: ['approvals'] }), qc.invalidateQueries({ queryKey: ['order-summary'] })]);
    } catch (e) {
      toast(errorMessage(e, t), 'danger');
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <View style={{ padding: space.lg, paddingBottom: 0, gap: space.sm }}>
        <SegmentedControl value={tab} onChange={(k) => { setTab(k); setSelected(new Set()); }}
          options={[{ key: 'pending', label: t('approvals.pending'), badge: summary.data?.pending }, { key: 'approved', label: t('approvals.approved') }, { key: 'rejected', label: t('approvals.rejected') }]} />
        {tab === 'pending' && orders.length > 0 && <T variant="caption" color={colors.muted}>{t('approvals.selectHint')}</T>}
      </View>
      {q.isLoading ? <LoadingView /> : q.isError && !orders.length ? <ErrorState error={q.error} onRetry={q.refetch} /> : (
        <FlatList
          data={orders} keyExtractor={(o) => o.id} contentContainerStyle={{ padding: space.lg, gap: space.md, flexGrow: 1, paddingBottom: 120 }}
          refreshControl={<RefreshControl refreshing={q.isRefetching && !q.isFetchingNextPage} onRefresh={() => q.refetch()} tintColor={colors.primary} />}
          onEndReached={() => q.hasNextPage && !q.isFetchingNextPage && q.fetchNextPage()}
          ListEmptyComponent={<EmptyState icon="checkmark-done-outline" title={t('approvals.empty')} subtitle={t('approvals.emptySub')} />}
          renderItem={({ item: o }) => (
            <Card selected={selected.has(o.id)} onLongPress={() => toggle(o)} onPress={() => (selected.size ? toggle(o) : router.push(`/manage/approvals/${o.id}`))}>
              <Row style={{ justifyContent: 'space-between' }}>
                <View style={{ flex: 1 }}>
                  <T variant="heading" numberOfLines={1}>{o.member?.name ?? o.member?.phone}</T>
                  <T variant="caption" color={colors.muted}>
                    {[o.member?.wing, o.member?.flat_no].filter(Boolean).join('-') || '—'} · {o.event_title}
                  </T>
                </View>
                <T variant="title" color={colors.primary}>{formatINR(o.total_amount)}</T>
              </Row>
              <T variant="caption" color={colors.muted} style={{ marginTop: 4 }}>{o.items.map((i) => `${i.qty}× ${i.tier_name}`).join(', ')}</T>
              <Row style={{ marginTop: 6, flexWrap: 'wrap' }}>
                <Badge tone="neutral" icon="receipt-outline" text={o.utr ?? t('approvals.flag.missing_utr')} />
                <FlagBadges flags={o.flags.filter((f) => f !== 'missing_utr' || !!o.utr)} />
                {o.has_screenshot && <Badge tone="info" icon="image" text={t('approvals.proof')} />}
                {selected.has(o.id) && <Ionicons name="checkmark-circle" size={20} color={colors.primary} />}
              </Row>
              <T variant="caption" color={colors.faint} style={{ marginTop: 4 }}>{formatDateTime(o.payment_submitted_at ?? o.created_at, i18n.language)}</T>
            </Card>
          )}
        />
      )}
      {selected.size > 0 && (
        <View style={{ position: 'absolute', bottom: 0, left: 0, right: 0, padding: space.lg, backgroundColor: colors.card, borderTopWidth: 1, borderTopColor: colors.border, gap: 6 }}>
          <Row>
            <Button title={t('common.cancel')} variant="secondary" onPress={() => setSelected(new Set())} style={{ flex: 1 }} />
            <Button title={t('approvals.bulkApprove', { n: selected.size })} variant="success" onPress={bulk} loading={busy} style={{ flex: 2 }} />
          </Row>
        </View>
      )}
    </View>
  );
}
