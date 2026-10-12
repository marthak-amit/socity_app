import React, { useState } from 'react';
import { FlatList, RefreshControl, ScrollView, View } from 'react-native';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { Button, Chip, EmptyState, ErrorState, LoadingView, Row } from '@/components/ui';
import { EventCard } from '@/components/EventCard';
import { flat, useEvents } from '@/hooks/queries';
import { useActiveSociety } from '@/hooks/useSociety';
import { colors, space } from '@/theme';

const FILTERS = ['all', 'draft', 'published', 'closed', 'cancelled'] as const;

export default function ManageEvents() {
  const { t } = useTranslation();
  const { societyId } = useActiveSociety();
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>('all');
  const q = useEvents(societyId, 'all');
  const events = flat(q.data).filter((e) => filter === 'all' || e.status === filter);

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <View style={{ padding: space.lg, paddingBottom: 0, gap: space.sm }}>
        <Button title={t('home.createEvent')} icon="add" onPress={() => router.push('/manage/event-form')} />
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <Row>{FILTERS.map((f) => <Chip key={f} label={f === 'all' ? t('common.all') : t(`eventAdmin.statusLabel.${f}`)} selected={filter === f} onPress={() => setFilter(f)} />)}</Row>
        </ScrollView>
      </View>
      {q.isLoading ? <LoadingView /> : q.isError && !events.length ? <ErrorState error={q.error} onRetry={q.refetch} /> : (
        <FlatList
          data={events} keyExtractor={(e) => e.id} contentContainerStyle={{ padding: space.lg, gap: space.md, flexGrow: 1 }}
          refreshControl={<RefreshControl refreshing={q.isRefetching} onRefresh={() => q.refetch()} tintColor={colors.primary} />}
          onEndReached={() => q.hasNextPage && q.fetchNextPage()}
          ListEmptyComponent={<EmptyState icon="calendar-outline" title={t('home.emptyUpcoming')} />}
          renderItem={({ item }) => <EventCard event={item} onPress={() => router.push(`/manage/event/${item.id}`)} />}
        />
      )}
    </View>
  );
}
