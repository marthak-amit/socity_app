import React, { useState } from 'react';
import { Modal, Pressable, View } from 'react-native';
import { Image } from 'expo-image';
import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { post } from '@/api/client';
import type { Order } from '@/api/types';
import { Badge, Banner, Button, Card, Chip, Divider, ErrorState, Input, Ionicons, LoadingView, Row, Screen, SectionTitle, T, confirm, errorMessage, toast } from '@/components/ui';
import { useOrder } from '@/hooks/queries';
import { useActiveSociety } from '@/hooks/useSociety';
import { colors, space } from '@/theme';
import { formatDateTime } from '@/utils/dates';
import { formatINR } from '@/utils/money';

export default function ApprovalDetail() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { societyId } = useActiveSociety();
  const q = useOrder(societyId, id);
  const o = q.data;
  const [reason, setReason] = useState('');
  const [rejecting, setRejecting] = useState(false);
  const [zoom, setZoom] = useState(false);
  const [busy, setBusy] = useState(false);

  if (q.isLoading) return <LoadingView />;
  if (q.isError || !o) return <ErrorState error={q.error} onRetry={q.refetch} />;

  const done = async (updated: Order, msg: string) => {
    qc.setQueryData(['order', societyId, id], updated);
    await Promise.all([qc.invalidateQueries({ queryKey: ['approvals'] }), qc.invalidateQueries({ queryKey: ['order-summary'] }), qc.invalidateQueries({ queryKey: ['event'] })]);
    toast(msg, 'success');
    router.back();
  };
  const approve = async () => {
    const flagged = o.flags.length > 0;
    if (!(await confirm(flagged ? t('approvals.includeFlagged') : t('common.approve'), t('approvals.approveConfirm'), t('common.approve')))) return;
    setBusy(true);
    try { await done(await post<Order>(`/societies/${societyId}/orders/${o.id}/approve`), t('common.approved')); }
    catch (e) { toast(errorMessage(e, t), 'danger'); void q.refetch(); } finally { setBusy(false); }
  };
  const reject = async () => {
    if (reason.trim().length < 3) return;
    setBusy(true);
    try { await done(await post<Order>(`/societies/${societyId}/orders/${o.id}/reject`, { reason: reason.trim() }), t('common.rejected')); }
    catch (e) { toast(errorMessage(e, t), 'danger'); } finally { setBusy(false); setRejecting(false); }
  };

  const quick = [t('approvals.quickReasons.notFound'), t('approvals.quickReasons.wrongAmount'), t('approvals.quickReasons.badProof'), t('approvals.quickReasons.duplicate')];
  const mismatch = o.paid_amount !== null && o.paid_amount !== o.total_amount;

  return (
    <Screen refreshing={q.isRefetching} onRefresh={() => q.refetch()} style={{ paddingBottom: 140 }}>
      {o.flags.map((f) => <Banner key={f} tone="warning" icon="flag" text={`${t(`approvals.flag.${f}`)} — ${t(`approvals.flagHelp.${f}`)}`} />)}
      <Card>
        <Row style={{ justifyContent: 'space-between' }}>
          <View style={{ flex: 1 }}>
            <T variant="heading">{o.member?.name ?? o.member?.phone}</T>
            <T variant="caption" color={colors.muted}>{o.member?.phone} · {[o.member?.wing, o.member?.flat_no].filter(Boolean).join('-')}</T>
          </View>
          <Badge tone={o.status === 'approved' ? 'success' : o.status === 'pending' ? 'warning' : 'danger'} text={t(`common.${o.status}`)} />
        </Row>
        <Divider />
        <T variant="caption" color={colors.muted}>{o.event_title} · {o.ref_code}</T>
        {o.items.map((it) => (
          <View key={it.tier_id} style={{ marginTop: 4 }}>
            <Row style={{ justifyContent: 'space-between' }}><T>{it.qty} × {it.tier_name}</T><T>{formatINR(it.qty * it.unit_price)}</T></Row>
            <T variant="caption" color={colors.muted}>{it.holders.map((h) => `${h.name}${h.type === 'guest' ? ' (G)' : ''}`).join(', ')}</T>
          </View>
        ))}
        <Divider />
        <Row style={{ justifyContent: 'space-between' }}><T variant="heading">{t('approvals.amount')}</T><T variant="title" color={colors.primary}>{formatINR(o.total_amount)}</T></Row>
        {o.paid_amount !== null && <Row style={{ justifyContent: 'space-between' }}><T variant="caption" color={colors.muted}>{t('approvals.claimed')}</T><T variant="label" color={mismatch ? colors.danger : colors.success}>{formatINR(o.paid_amount)}</T></Row>}
        <Row style={{ justifyContent: 'space-between', marginTop: 4 }}><T variant="caption" color={colors.muted}>{t('approvals.utr')}</T><T variant="label" selectable>{o.utr ?? '—'}</T></Row>
        {o.payment_submitted_at && <T variant="caption" color={colors.faint} style={{ marginTop: 4 }}>{formatDateTime(o.payment_submitted_at, i18n.language)}</T>}
        {o.reject_reason && <Banner tone="danger" text={o.reject_reason} />}
      </Card>

      <SectionTitle>{t('approvals.proof')}</SectionTitle>
      {o.screenshot_url ? (
        <Pressable onPress={() => setZoom(true)}>
          <Image source={{ uri: o.screenshot_url }} style={{ height: 360, borderRadius: 12, backgroundColor: colors.border }} contentFit="contain" />
        </Pressable>
      ) : <Banner tone="neutral" icon="image-outline" text={t('approvals.noScreenshot')} />}

      <Modal visible={zoom} transparent animationType="fade" onRequestClose={() => setZoom(false)}>
        <Pressable style={{ flex: 1, backgroundColor: '#000' }} onPress={() => setZoom(false)}>
          {o.screenshot_url && <Image source={{ uri: o.screenshot_url }} style={{ flex: 1 }} contentFit="contain" />}
          <Ionicons name="close" size={32} color="#fff" style={{ position: 'absolute', top: 48, right: 16 }} />
        </Pressable>
      </Modal>

      <Modal visible={rejecting} transparent animationType="slide" onRequestClose={() => setRejecting(false)}>
        <View style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' }}>
          <View style={{ backgroundColor: colors.bg, padding: space.lg, gap: space.md, borderTopLeftRadius: 24, borderTopRightRadius: 24, paddingBottom: space.xxl }}>
            <T variant="title">{t('approvals.rejectTitle')}</T>
            <Row style={{ flexWrap: 'wrap' }}>{quick.map((r) => <Chip key={r} label={r} selected={reason === r} onPress={() => setReason(r)} />)}</Row>
            <Input label={t('approvals.rejectReason')} value={reason} onChangeText={setReason} maxLength={300} />
            <Row>
              <Button title={t('common.cancel')} variant="secondary" style={{ flex: 1 }} onPress={() => setRejecting(false)} />
              <Button title={t('common.reject')} variant="danger" style={{ flex: 1 }} onPress={reject} loading={busy} disabled={reason.trim().length < 3} />
            </Row>
          </View>
        </View>
      </Modal>

      {o.status === 'pending' && (
        <View style={{ marginTop: space.md }}>
          {!o.payment_submitted_at && <Banner tone="info" text={t('errors.payment_not_submitted')} />}
          <Row style={{ marginTop: space.sm }}>
            <Button title={t('common.reject')} variant="danger" icon="close" style={{ flex: 1 }} onPress={() => setRejecting(true)} />
            <Button title={o.flags.length ? t('approvals.includeFlagged') : t('common.approve')} variant="success" icon="checkmark" style={{ flex: 1 }} onPress={approve} loading={busy} disabled={!o.payment_submitted_at} />
          </Row>
        </View>
      )}
    </Screen>
  );
}
