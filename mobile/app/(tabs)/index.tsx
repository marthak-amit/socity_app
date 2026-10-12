import React, { useState } from 'react';
import { FlatList, RefreshControl, View } from 'react-native';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { Banner, Button, EmptyState, ErrorState, LoadingView, SegmentedControl } from '@/components/ui';
import { EventCard } from '@/components/EventCard';
import { flat, useEvents } from '@/hooks/queries';
import { useActiveSociety } from '@/hooks/useSociety';
import { colors, space } from '@/theme';
import { isAdmin } from '@/utils/roles';

export default function Home() {
  const { t } = useTranslation();
  const { societyId, role, suspended } = useActiveSociety();
  const [when, setWhen] = useState<'upcoming' | 'past'>('upcoming');
  const q = useEvents(societyId, when);
  const events = flat(q.data);

  if (suspended) return <View style={{ flex: 1, backgroundColor: colors.bg }}><EmptyState icon="pause-circle-outline" title={t('home.suspendedTitle')} subtitle={t('home.suspendedBody')} /></View>;

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <View style={{ padding: space.lg, paddingBottom: 0, gap: space.sm }}>
        <SegmentedControl value={when} onChange={setWhen} options={[{ key: 'upcoming', label: t('home.upcoming') }, { key: 'past', label: t('home.past') }]} />
        {isAdmin(role) && <Button title={t('home.createEvent')} icon="add" variant="secondary" size="sm" onPress={() => router.push('/manage/event-form')} />}
      </View>
      {q.isLoading ? <LoadingView /> : q.isError && !events.length ? <ErrorState error={q.error} onRetry={q.refetch} /> : (
        <FlatList
          data={events} keyExtractor={(e) => e.id}
          renderItem={({ item }) => <EventCard event={item} />}
          contentContainerStyle={{ padding: space.lg, gap: space.md, flexGrow: 1 }}
          refreshControl={<RefreshControl refreshing={q.isRefetching && !q.isFetchingNextPage} onRefresh={() => q.refetch()} tintColor={colors.primary} />}
          onEndReached={() => q.hasNextPage && !q.isFetchingNextPage && q.fetchNextPage()} onEndReachedThreshold={0.5}
          ListEmptyComponent={<EmptyState icon="calendar-outline" title={when === 'upcoming' ? t('home.emptyUpcoming') : t('home.emptyPast')} subtitle={when === 'upcoming' ? t('home.emptyUpcomingSub') : undefined} />}
          ListFooterComponent={q.isFetchingNextPage ? <LoadingView /> : q.isError ? <Banner tone="danger" text={t('common.offline')} /> : null}
        />
      )}
    </View>
  );
}
