import React from 'react';
import { View } from 'react-native';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { get } from '@/api/client';
import type { Page } from '@/api/types';
import { Badge, Banner, Card, Ionicons, Row, Screen, T } from '@/components/ui';
import { useOrderSummary } from '@/hooks/queries';
import { useActiveSociety, useSocietyDetail } from '@/hooks/useSociety';
import { colors, space } from '@/theme';

type Item = { icon: React.ComponentProps<typeof Ionicons>['name']; title: string; route: string; badge?: React.ReactNode; tint: string };

function useCount(societyId: string | undefined, path: string, query: Record<string, string>) {
  return useQuery({
    queryKey: ['count', societyId, path, query], enabled: !!societyId, refetchInterval: 60_000,
    queryFn: async () => (await get<Page<unknown>>(`/societies/${societyId}${path}`, { ...query, limit: 1 })).total,
  });
}

export default function Manage() {
  const { t } = useTranslation();
  const { societyId, role } = useActiveSociety();
  const society = useSocietyDetail(societyId);
  const summary = useOrderSummary(societyId);
  const joinReqs = useCount(societyId, '/members', { status: 'pending' });
  const photos = useCount(societyId, '/gallery', { status: 'pending' });
  const refresh = () => Promise.all([society.refetch(), summary.refetch(), joinReqs.refetch(), photos.refetch()]);
  const pend = summary.data?.pending ?? 0;

  const items: Item[] = [
    { icon: 'checkmark-done-circle', tint: colors.success, title: t('manage.approvals'), route: '/manage/approvals',
      badge: pend ? <Row gap={4}><Badge tone="danger" text={t('manage.pendingCount', { n: pend })} />{summary.data?.pending_flagged ? <Badge tone="warning" icon="flag" text={String(summary.data.pending_flagged)} /> : null}</Row> : undefined },
    { icon: 'calendar', tint: colors.primary, title: t('manage.events'), route: '/manage/events' },
    { icon: 'people', tint: colors.info, title: t('manage.members'), route: '/manage/members',
      badge: joinReqs.data ? <Badge tone="danger" text={t('manage.pendingCount', { n: joinReqs.data })} /> : undefined },
    { icon: 'images', tint: '#DB2777', title: t('manage.galleryMod'), route: '/manage/moderation',
      badge: photos.data ? <Badge tone="danger" text={t('manage.pendingCount', { n: photos.data })} /> : undefined },
    { icon: 'qr-code', tint: colors.warning, title: t('manage.invite'), route: '/manage/invite' },
    { icon: 'settings', tint: colors.muted, title: t('manage.settings'), route: '/manage/society' },
  ];

  return (
    <Screen refreshing={society.isRefetching} onRefresh={refresh}>
      {society.data?.warnings.map((w) => (
        <Banner key={w} tone="warning" text={t(`manage.warnings.${w}`)} />
      ))}
      <T variant="caption" color={colors.muted}>{t('common.youAre', { role: t(`roles.${role ?? 'member'}`) })}</T>
      {items.map((it) => (
        <Card key={it.route} onPress={() => router.push(it.route as never)}>
          <Row gap={space.md}>
            <View style={{ width: 44, height: 44, borderRadius: 12, backgroundColor: `${it.tint}1A`, alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name={it.icon} size={24} color={it.tint} />
            </View>
            <View style={{ flex: 1, gap: 2 }}>
              <T variant="heading">{it.title}</T>
              {it.badge}
            </View>
            <Ionicons name="chevron-forward" size={20} color={colors.faint} />
          </Row>
        </Card>
      ))}
    </Screen>
  );
}
