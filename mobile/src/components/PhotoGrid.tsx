import React, { useState } from 'react';
import { Dimensions, FlatList, Modal, Pressable, View } from 'react-native';
import { Image } from 'expo-image';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';
import type { GalleryItem } from '@/api/types';
import { Badge, Button, Ionicons, T } from '@/components/ui';
import { colors, space } from '@/theme';

const GAP = 3;
const COLS = 3;

/** Thumbnail grid + full-screen viewer. Non-scrolling by default so it can sit inside a ScrollView. */
export function PhotoGrid({ items, onDelete, canDelete, renderOverlay }: {
  items: GalleryItem[]; onDelete?: (g: GalleryItem) => void; canDelete?: (g: GalleryItem) => boolean; renderOverlay?: (g: GalleryItem) => React.ReactNode;
}) {
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  const [viewing, setViewing] = useState<number | null>(null);
  const size = (Dimensions.get('window').width - GAP * (COLS + 1)) / COLS;
  const current = viewing !== null ? items[viewing] : null;

  return (
    <>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: GAP }}>
        {items.map((g, i) => (
          <Pressable key={g.id} onPress={() => setViewing(i)} style={{ width: size, height: size }} accessibilityRole="imagebutton">
            <Image source={{ uri: g.thumb_url }} style={{ width: size, height: size, backgroundColor: colors.border }} contentFit="cover" recyclingKey={g.id} />
            {g.status !== 'approved' && <View style={{ position: 'absolute', top: 4, left: 4 }}><Badge text={t(g.status === 'pending' ? 'gallery.pendingBadge' : 'gallery.rejectedBadge')} tone={g.status === 'pending' ? 'warning' : 'danger'} /></View>}
            {renderOverlay?.(g)}
          </Pressable>
        ))}
      </View>
      <Modal visible={current !== null} transparent animationType="fade" onRequestClose={() => setViewing(null)}>
        <View style={{ flex: 1, backgroundColor: '#000' }}>
          {viewing !== null && (
            <FlatList
              data={items} horizontal pagingEnabled initialScrollIndex={viewing} keyExtractor={(g) => g.id} scrollEnabled
              getItemLayout={(_, i) => ({ length: Dimensions.get('window').width, offset: Dimensions.get('window').width * i, index: i })}
              onMomentumScrollEnd={(e) => setViewing(Math.round(e.nativeEvent.contentOffset.x / Dimensions.get('window').width))}
              renderItem={({ item }) => (
                <Image source={{ uri: item.url }} style={{ width: Dimensions.get('window').width, height: '100%' }} contentFit="contain" />
              )}
            />
          )}
          <View style={{ position: 'absolute', top: insets.top + 8, right: 12, flexDirection: 'row', gap: space.md }}>
            {current && onDelete && (canDelete ? canDelete(current) : true) ? (
              <Pressable onPress={() => { onDelete(current); setViewing(null); }} hitSlop={10}><Ionicons name="trash-outline" size={26} color="#fff" /></Pressable>
            ) : null}
            <Pressable onPress={() => setViewing(null)} hitSlop={10} accessibilityLabel={t('common.close')}><Ionicons name="close" size={30} color="#fff" /></Pressable>
          </View>
          {current && (
            <View style={{ position: 'absolute', bottom: insets.bottom + 16, left: 16, right: 16 }}>
              <T color="#fff" variant="caption">{t('gallery.by', { name: current.uploaded_by.name ?? '—' })}</T>
            </View>
          )}
        </View>
      </Modal>
    </>
  );
}

export function UploadButton({ onPress, loading, title }: { onPress: () => void; loading?: boolean; title: string }) {
  return <Button title={title} icon="cloud-upload-outline" onPress={onPress} loading={loading} variant="secondary" />;
}
