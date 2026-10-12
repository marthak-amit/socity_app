import React from 'react';
import { FlatList, RefreshControl, View } from 'react-native';
import { Image } from 'expo-image';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { post } from '@/api/client';
import type { GalleryItem } from '@/api/types';
import { Button, Card, EmptyState, ErrorState, LoadingView, Row, T, errorMessage, toast } from '@/components/ui';
import { flat, useGallery } from '@/hooks/queries';
import { useActiveSociety } from '@/hooks/useSociety';
import { colors, space } from '@/theme';
import { formatDateTime } from '@/utils/dates';

export default function Moderation() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const { societyId } = useActiveSociety();
  const q = useGallery(societyId, { status: 'pending' });
  const items = flat(q.data);

  const act = async (g: GalleryItem, action: 'approve' | 'reject') => {
    try {
      await post(`/societies/${societyId}/gallery/${g.id}/${action}`);
      await Promise.all([qc.invalidateQueries({ queryKey: ['gallery'] }), qc.invalidateQueries({ queryKey: ['count'] })]);
    } catch (e) {
      toast(errorMessage(e, t), 'danger');
    }
  };

  if (q.isLoading) return <LoadingView />;
  if (q.isError && !items.length) return <ErrorState error={q.error} onRetry={q.refetch} />;
  return (
    <FlatList
      data={items} keyExtractor={(g) => g.id} contentContainerStyle={{ padding: space.lg, gap: space.md, flexGrow: 1 }}
      refreshControl={<RefreshControl refreshing={q.isRefetching} onRefresh={() => q.refetch()} tintColor={colors.primary} />}
      onEndReached={() => q.hasNextPage && q.fetchNextPage()}
      ListEmptyComponent={<EmptyState icon="images-outline" title={t('moderation.empty')} />}
      renderItem={({ item: g }) => (
        <Card style={{ padding: 0, overflow: 'hidden' }}>
          <Image source={{ uri: g.url }} style={{ height: 260, backgroundColor: colors.border }} contentFit="cover" />
          <View style={{ padding: space.md, gap: space.sm }}>
            <T variant="caption" color={colors.muted}>{t('moderation.uploadedBy', { name: g.uploaded_by.name ?? '—' })} · {formatDateTime(g.created_at, i18n.language)}</T>
            <Row>
              <Button title={t('moderation.reject')} variant="secondary" style={{ flex: 1 }} onPress={() => act(g, 'reject')} />
              <Button title={t('moderation.approve')} variant="success" style={{ flex: 1 }} onPress={() => act(g, 'approve')} />
            </Row>
          </View>
        </Card>
      )}
    />
  );
}
