import React, { useState } from 'react';
import { Modal, Pressable, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { del, get, post } from '@/api/client';
import type { EventT, Member, Page } from '@/api/types';
import { Avatar, Badge, Banner, Button, Card, ErrorState, Input, Ionicons, LoadingView, Row, Screen, SectionTitle, T, confirm, errorMessage, toast } from '@/components/ui';
import { useEvent, useReport, useVolunteers } from '@/hooks/queries';
import { useActiveSociety } from '@/hooks/useSociety';
import { colors, radius, space } from '@/theme';
import { formatDateTime } from '@/utils/dates';
import { formatINR } from '@/utils/money';

export default function ManageEvent() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { societyId } = useActiveSociety();
  const q = useEvent(societyId, id);
  const report = useReport(societyId, id);
  const vols = useVolunteers(societyId, id);
  const [picker, setPicker] = useState(false);
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const members = useQuery({
    queryKey: ['member-picker', societyId, search], enabled: picker && !!societyId,
    queryFn: () => get<Page<Member>>(`/societies/${societyId}/members`, { status: 'active', q: search.trim() || undefined, limit: 30 }),
  });
  const ev = q.data;
  if (q.isLoading) return <LoadingView />;
  if (q.isError || !ev) return <ErrorState error={q.error} onRetry={q.refetch} />;

  const base = `/societies/${societyId}/events/${ev.id}`;
  const refresh = () => Promise.all([qc.invalidateQueries({ queryKey: ['event'] }), qc.invalidateQueries({ queryKey: ['events'] }), qc.invalidateQueries({ queryKey: ['report'] })]);
  const run = async (fn: () => Promise<unknown>, after?: () => void) => {
    setBusy(true);
    try { await fn(); await refresh(); after?.(); } catch (e) { toast(errorMessage(e, t), 'danger'); } finally { setBusy(false); }
  };
  const transition = (action: 'publish' | 'close' | 'reopen' | 'cancel', confirmText?: string, destructive = false) => async () => {
    if (confirmText && !(await confirm(t(`eventAdmin.${action}`), confirmText, t('common.confirm'), destructive))) return;
    await run(() => post<EventT>(`${base}/${action}`));
  };
  const removeDraft = async () => {
    if (!(await confirm(t('eventAdmin.delete'), t('eventAdmin.deleteConfirm'), t('common.delete'), true))) return;
    await run(() => del(base), () => router.back());
  };
  const addVolunteer = async (m: Member) => {
    setPicker(false);
    await run(async () => { await post(`${base}/volunteers`, { user_id: m.user_id }); await vols.refetch(); }, () => toast(t('common.done'), 'success'));
  };
  const removeVolunteer = async (userId: string) => run(async () => { await del(`${base}/volunteers/${userId}`); await vols.refetch(); });

  const tot = report.data?.totals;
  const tone = ev.status === 'published' ? 'success' : ev.status === 'draft' ? 'warning' : ev.status === 'cancelled' ? 'danger' : 'neutral';

  return (
    <Screen refreshing={q.isRefetching} onRefresh={() => { void q.refetch(); void report.refetch(); void vols.refetch(); }}>
      <Card>
        <Row style={{ justifyContent: 'space-between' }}>
          <View style={{ flex: 1 }}><T variant="title">{ev.title}</T><T variant="caption" color={colors.muted}>{formatDateTime(ev.starts_at, i18n.language)}</T></View>
          <Badge tone={tone} text={t(`eventAdmin.statusLabel.${ev.status}`)} />
        </Row>
        {tot && (
          <Row gap={space.lg} style={{ marginTop: space.md }}>
            <View><T variant="title" color={colors.success}>{formatINR(tot.collected_amount)}</T><T variant="caption" color={colors.muted}>{t('report.collected')}</T></View>
            <View><T variant="title">{tot.passes_sold}</T><T variant="caption" color={colors.muted}>{t('report.passesSold')}</T></View>
            <View><T variant="title" color={tot.pending_count ? colors.danger : colors.text}>{tot.pending_count}</T><T variant="caption" color={colors.muted}>{t('common.pending')}</T></View>
          </Row>
        )}
      </Card>

      <Row style={{ flexWrap: 'wrap' }}>
        <Button title={t('common.edit')} icon="create-outline" variant="secondary" onPress={() => router.push({ pathname: '/manage/event-form', params: { id: ev.id } })} />
        <Button title={t('eventAdmin.report')} icon="stats-chart" variant="secondary" onPress={() => router.push(`/manage/report/${ev.id}`)} />
        <Button title={t('event.getPasses')} icon="eye-outline" variant="ghost" onPress={() => router.push(`/event/${ev.id}`)} />
      </Row>

      {ev.status === 'draft' && <Button title={t('eventAdmin.publish')} icon="rocket" onPress={transition('publish', t('eventAdmin.publishConfirm'))} loading={busy} />}
      {ev.status === 'published' && <Button title={t('eventAdmin.close')} variant="secondary" icon="lock-closed-outline" onPress={transition('close')} loading={busy} />}
      {ev.status === 'closed' && <Button title={t('eventAdmin.reopen')} variant="secondary" icon="lock-open-outline" onPress={transition('reopen')} loading={busy} />}
      {ev.status !== 'cancelled' && ev.status !== 'draft' && <Button title={t('eventAdmin.cancel')} variant="danger" icon="close-circle-outline" onPress={transition('cancel', t('eventAdmin.cancelConfirm'), true)} loading={busy} />}
      {ev.status === 'draft' && <Button title={t('eventAdmin.delete')} variant="ghost" onPress={removeDraft} />}

      <SectionTitle right={ev.status !== 'cancelled' ? <Button title={t('eventAdmin.addVolunteer')} icon="person-add-outline" size="sm" variant="secondary" onPress={() => setPicker(true)} /> : undefined}>{t('eventAdmin.volunteers')}</SectionTitle>
      <T variant="caption" color={colors.muted}>{t('eventAdmin.volunteerHelp')}</T>
      {vols.data?.length ? vols.data.map((v) => (
        <Card key={v.user_id}>
          <Row gap={space.md}>
            <Avatar name={v.name ?? v.phone} />
            <View style={{ flex: 1 }}>
              <T variant="heading">{v.name ?? v.phone}</T>
              <T variant="caption" color={v.active ? colors.muted : colors.danger}>{t('eventAdmin.expires', { date: formatDateTime(v.expires_at, i18n.language) })}</T>
            </View>
            <Pressable onPress={() => removeVolunteer(v.user_id)} hitSlop={10}><Ionicons name="close-circle" size={24} color={colors.faint} /></Pressable>
          </Row>
        </Card>
      )) : <Banner tone="neutral" icon="people-outline" text={t('eventAdmin.noVolunteers')} />}

      <Button title={t('eventAdmin.approvals')} icon="checkmark-done" variant="secondary" onPress={() => router.push('/manage/approvals')} />

      <Modal visible={picker} transparent animationType="slide" onRequestClose={() => setPicker(false)}>
        <View style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' }}>
          <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: radius.xl, borderTopRightRadius: radius.xl, padding: space.lg, gap: space.sm, maxHeight: '75%' }}>
            <T variant="title">{t('eventAdmin.pickMember')}</T>
            <Input value={search} onChangeText={setSearch} placeholder={t('members.searchPlaceholder')} autoCapitalize="none" />
            <Screen scroll padded={false} style={{ gap: 8 }}>
              {(members.data?.items ?? []).map((m) => (
                <Card key={m.id} onPress={() => addVolunteer(m)}>
                  <Row gap={space.md}><Avatar name={m.name ?? m.phone} /><View style={{ flex: 1 }}><T variant="heading">{m.name ?? m.phone}</T><T variant="caption" color={colors.muted}>{m.phone}</T></View></Row>
                </Card>
              ))}
            </Screen>
            <Button title={t('common.cancel')} variant="ghost" onPress={() => setPicker(false)} />
          </View>
        </View>
      </Modal>
    </Screen>
  );
}
