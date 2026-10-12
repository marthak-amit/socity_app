import React, { useMemo } from 'react';
import { SectionList, RefreshControl, View } from 'react-native';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { Badge, Banner, Card, EmptyState, ErrorState, Ionicons, LoadingView, Row, T } from '@/components/ui';
import { useMyPasses } from '@/hooks/usePasses';
import type { PassT } from '@/api/types';
import { colors, space } from '@/theme';
import { formatDateRange, formatDateTime } from '@/utils/dates';

export default function Passes() {
  const { t, i18n } = useTranslation();
  const q = useMyPasses();
  const passes = q.data?.passes ?? [];

  const sections = useMemo(() => {
    const now = Date.now();
    const byEvent = new Map<string, PassT[]>();
    for (const p of passes) byEvent.set(p.event.id, [...(byEvent.get(p.event.id) ?? []), p]);
    const groups = [...byEvent.values()].map((items) => ({ event: items[0].event, data: items }));
    const upcoming = groups.filter((g) => new Date(g.event.ends_at).getTime() >= now).sort((a, b) => +new Date(a.event.starts_at) - +new Date(b.event.starts_at));
    const past = groups.filter((g) => new Date(g.event.ends_at).getTime() < now).sort((a, b) => +new Date(b.event.starts_at) - +new Date(a.event.starts_at));
    return [...upcoming.map((g) => ({ ...g, title: t('passes.upcoming') })), ...past.map((g) => ({ ...g, title: t('passes.past') }))];
  }, [passes, t]);

  if (q.isLoading) return <LoadingView />;
  if (q.isError && !passes.length) return <ErrorState error={q.error} onRetry={q.refetch} />;

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      {q.data?.offline && <View style={{ padding: space.lg, paddingBottom: 0 }}><Banner tone="warning" icon="cloud-offline" text={t('passes.offlineBanner')} /></View>}
      <SectionList
        sections={sections} keyExtractor={(p) => p.id} stickySectionHeadersEnabled={false}
        contentContainerStyle={{ padding: space.lg, gap: space.sm, flexGrow: 1 }}
        refreshControl={<RefreshControl refreshing={q.isRefetching} onRefresh={() => q.refetch()} tintColor={colors.primary} />}
        ListEmptyComponent={<EmptyState icon="ticket-outline" title={t('passes.empty')} subtitle={t('passes.emptySub')} />}
        renderSectionHeader={({ section }) => (
          <View style={{ marginTop: space.md, gap: 2 }}>
            <T variant="caption" color={colors.muted}>{section.title.toUpperCase()}</T>
            <T variant="heading">{section.event.title}</T>
            <T variant="caption" color={colors.muted}>{section.event.society_name} · {formatDateRange(section.event.starts_at, section.event.ends_at, i18n.language)}</T>
          </View>
        )}
        renderItem={({ item, index, section }) => (
          <Card onPress={() => router.push({ pathname: '/pass/[id]', params: { id: item.id } })} style={item.status === 'revoked' ? { opacity: 0.55 } : undefined}>
            <Row gap={space.md}>
              <View style={{ width: 44, height: 44, borderRadius: 12, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' }}>
                <Ionicons name="qr-code" size={24} color={colors.primary} />
              </View>
              <View style={{ flex: 1 }}>
                <T variant="heading" numberOfLines={1}>{item.holder_name}</T>
                <T variant="caption" color={colors.muted}>{item.tier_name}{item.holder_type === 'guest' ? ` · ${t('passes.guest')}` : ''} · {t('passes.ticketOf', { i: index + 1, n: section.data.length })}</T>
                {item.scanned_dates.length > 0 && <T variant="caption" color={colors.success}>{t('passes.scannedOn', { date: formatDateTime(item.created_at, i18n.language).split(',')[0] })}</T>}
              </View>
              {item.status === 'revoked' ? <Badge tone="danger" text={t('passes.revoked')} /> : item.scanned_dates.length > 0 ? <Badge tone="success" text={t('passes.used')} /> : <Ionicons name="chevron-forward" size={20} color={colors.faint} />}
            </Row>
          </Card>
        )}
      />
    </View>
  );
}
