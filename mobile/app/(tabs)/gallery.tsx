import React, { useState } from 'react';
import { ScrollView, View } from 'react-native';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { del } from '@/api/client';
import type { GalleryItem } from '@/api/types';
import { Button, Chip, EmptyState, ErrorState, LoadingView, Row, Screen, SegmentedControl, confirm, errorMessage, toast } from '@/components/ui';
import { PhotoGrid } from '@/components/PhotoGrid';
import { flat, useEvents, useGallery } from '@/hooks/queries';
import { useGalleryUpload } from '@/hooks/useGalleryUpload';
import { useActiveSociety } from '@/hooks/useSociety';
import { space } from '@/theme';
import { isAdmin } from '@/utils/roles';

export default function GalleryTab() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { societyId, role } = useActiveSociety();
  const [eventId, setEventId] = useState<string | undefined>();
  const [mine, setMine] = useState<'all' | 'mine'>('all');
  const events = useEvents(societyId, 'past');
  const q = useGallery(societyId, { event_id: eventId, mine: mine === 'mine' });
  const upload = useGalleryUpload(societyId, eventId);
  const items = flat(q.data);

  const remove = async (g: GalleryItem) => {
    if (!(await confirm(t('gallery.delete'), t('gallery.deleteConfirm'), t('common.delete'), true))) return;
    try {
      await del(`/societies/${societyId}/gallery/${g.id}`);
      await qc.invalidateQueries({ queryKey: ['gallery'] });
    } catch (e) {
      toast(errorMessage(e, t), 'danger');
    }
  };

  return (
    <Screen refreshing={q.isRefetching && !q.isFetchingNextPage} onRefresh={() => q.refetch()} padded={false} style={{ paddingTop: space.md }}>
      <View style={{ paddingHorizontal: space.lg, gap: space.sm }}>
        <SegmentedControl value={mine} onChange={setMine} options={[{ key: 'all', label: t('gallery.all') }, { key: 'mine', label: t('gallery.mine') }]} />
        <Button title={t('gallery.upload')} icon="cloud-upload-outline" variant="secondary" onPress={upload.pick} loading={upload.loading} />
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <Row>
            <Chip label={t('gallery.allEvents')} selected={!eventId} onPress={() => setEventId(undefined)} />
            {flat(events.data).map((e) => <Chip key={e.id} label={e.title} selected={eventId === e.id} onPress={() => setEventId(e.id)} />)}
          </Row>
        </ScrollView>
      </View>
      {q.isLoading ? <LoadingView /> : q.isError && !items.length ? <ErrorState error={q.error} onRetry={q.refetch} /> : items.length === 0 ? (
        <EmptyState icon="images-outline" title={t('gallery.empty')} subtitle={t('gallery.emptySub')} />
      ) : (
        <>
          <PhotoGrid items={items} onDelete={remove} canDelete={(g) => g.mine || isAdmin(role)} />
          {q.hasNextPage && <View style={{ padding: space.lg }}><Button title={t('common.seeMore')} variant="secondary" onPress={() => q.fetchNextPage()} loading={q.isFetchingNextPage} /></View>}
        </>
      )}
    </Screen>
  );
}
