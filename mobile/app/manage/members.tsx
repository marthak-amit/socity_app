import React, { useState } from 'react';
import { FlatList, Modal, Pressable, RefreshControl, View } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { del, patch, post } from '@/api/client';
import type { Member } from '@/api/types';
import { Avatar, Badge, Banner, Button, Card, EmptyState, ErrorState, Input, LoadingView, Row, SegmentedControl, T, confirm, errorMessage, toast } from '@/components/ui';
import { flat, useMembers } from '@/hooks/queries';
import { useActiveSociety } from '@/hooks/useSociety';
import { colors, radius, space } from '@/theme';
import { Role, assignableRoles } from '@/utils/roles';

export default function Members() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { societyId, role } = useActiveSociety();
  const [tab, setTab] = useState<'pending' | 'active'>('pending');
  const [search, setSearch] = useState('');
  const [sheet, setSheet] = useState<Member | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const q = useMembers(societyId, tab, search.trim());
  const pendingCount = useMembers(societyId, 'pending');
  const members = flat(q.data);

  const refresh = () => Promise.all([qc.invalidateQueries({ queryKey: ['members'] }), qc.invalidateQueries({ queryKey: ['count'] })]);
  const act = async (fn: () => Promise<unknown>, okMsg?: string) => {
    try { const r = await fn(); await refresh(); if (okMsg) toast(okMsg, 'success'); return r; } catch (e) { toast(errorMessage(e, t), 'danger'); }
  };
  const approve = (m: Member) => act(() => post(`/societies/${societyId}/members/${m.id}/approve`), t('common.approved'));
  const reject = (m: Member) => act(() => post(`/societies/${societyId}/members/${m.id}/reject`), t('common.rejected'));
  const changeRole = async (m: Member, r: Role) => {
    const res = await act(() => patch<{ warnings: string[] }>(`/societies/${societyId}/members/${m.id}`, { role: r }));
    if (res) setWarnings((res as { warnings: string[] }).warnings);
    setSheet(null);
  };
  const remove = async (m: Member) => {
    if (!(await confirm(t('members.removeMember'), t('members.removeConfirm', { name: m.name ?? m.phone }), t('common.remove'), true))) return;
    const res = await act(() => del<{ warnings: string[] }>(`/societies/${societyId}/members/${m.id}`));
    if (res) setWarnings((res as { warnings: string[] }).warnings);
    setSheet(null);
  };

  const importCsv = async () => {
    const picked = await DocumentPicker.getDocumentAsync({ type: ['text/csv', 'text/comma-separated-values', 'text/plain', '*/*'], copyToCacheDirectory: true });
    if (picked.canceled) return;
    try {
      const text = await (await fetch(picked.assets[0].uri)).text();
      const r = await post<{ created: number; updated: number; activated: number; errors: unknown[] }>(`/societies/${societyId}/members/import`, { csv_text: text });
      await refresh();
      toast(`${t('members.importResult', r)}${r.errors.length ? ` · ${t('members.importErrors', { n: r.errors.length })}` : ''}`, r.errors.length ? 'neutral' : 'success');
    } catch (e) {
      toast(errorMessage(e, t), 'danger');
    }
  };

  const roleLabel = (r: Role) => (r === 'admin' ? t('members.makeAdmin') : r === 'volunteer' ? t('members.makeVolunteer') : t('members.makeMember'));

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <View style={{ padding: space.lg, paddingBottom: 0, gap: space.sm }}>
        <SegmentedControl value={tab} onChange={setTab} options={[{ key: 'pending', label: t('members.requests'), badge: pendingCount.data?.pages[0]?.total }, { key: 'active', label: t('members.active') }]} />
        {tab === 'active' && <Input value={search} onChangeText={setSearch} placeholder={t('members.searchPlaceholder')} autoCapitalize="none" />}
        {warnings.includes('min_two_admins') && <Banner tone="warning" text={t('members.minTwoAdmins')} />}
      </View>
      {q.isLoading ? <LoadingView /> : q.isError && !members.length ? <ErrorState error={q.error} onRetry={q.refetch} /> : (
        <FlatList
          data={members} keyExtractor={(m) => m.id} contentContainerStyle={{ padding: space.lg, gap: space.sm, flexGrow: 1 }}
          refreshControl={<RefreshControl refreshing={q.isRefetching && !q.isFetchingNextPage} onRefresh={() => refresh()} tintColor={colors.primary} />}
          onEndReached={() => q.hasNextPage && !q.isFetchingNextPage && q.fetchNextPage()}
          ListEmptyComponent={<EmptyState icon="people-outline" title={tab === 'pending' ? t('members.noRequests') : t('members.empty')} />}
          ListFooterComponent={tab === 'active' ? (
            <View style={{ marginTop: space.lg, gap: 6 }}>
              <Button title={t('members.importCsv')} icon="document-text-outline" variant="secondary" onPress={importCsv} />
              <T variant="caption" color={colors.muted}>{t('members.importHelp')}</T>
            </View>
          ) : null}
          renderItem={({ item: m }) => {
            const canManage = assignableRoles(role, m.role).length > 0 || (role === 'owner' && m.role !== 'owner');
            return (
              <Card onPress={tab === 'active' && canManage ? () => setSheet(m) : undefined}>
                <Row gap={space.md}>
                  <Avatar name={m.name ?? m.phone} />
                  <View style={{ flex: 1 }}>
                    <T variant="heading" numberOfLines={1}>{m.name ?? m.phone}</T>
                    <T variant="caption" color={colors.muted}>{m.phone}{m.flat_no || m.wing ? ` · ${[m.wing, m.flat_no].filter(Boolean).join('-')}` : ''}</T>
                  </View>
                  {tab === 'active' && m.role !== 'member' && <Badge tone={m.role === 'volunteer' ? 'info' : 'primary'} text={t(`roles.${m.role}`)} />}
                </Row>
                {tab === 'pending' && (
                  <Row style={{ marginTop: space.md }}>
                    <Button title={t('common.reject')} variant="secondary" style={{ flex: 1 }} size="sm" onPress={() => reject(m)} />
                    <Button title={t('common.approve')} variant="success" style={{ flex: 1 }} size="sm" onPress={() => approve(m)} />
                  </Row>
                )}
              </Card>
            );
          }}
        />
      )}
      <Modal visible={!!sheet} transparent animationType="slide" onRequestClose={() => setSheet(null)}>
        <Pressable style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' }} onPress={() => setSheet(null)}>
          <Pressable style={{ backgroundColor: colors.bg, borderTopLeftRadius: radius.xl, borderTopRightRadius: radius.xl, padding: space.lg, gap: space.sm, paddingBottom: space.xxl }}>
            <T variant="title">{sheet?.name ?? sheet?.phone}</T>
            <T variant="caption" color={colors.muted}>{t('members.changeRole')}</T>
            {sheet && assignableRoles(role, sheet.role).map((r) => <Button key={r} title={roleLabel(r)} variant="secondary" onPress={() => changeRole(sheet, r)} />)}
            {sheet && <Button title={t('members.removeMember')} variant="danger" onPress={() => remove(sheet)} />}
            <Button title={t('common.cancel')} variant="ghost" onPress={() => setSheet(null)} />
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}
