import { useState } from 'react';
import * as ImagePicker from 'expo-image-picker';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { post, uploadImage } from '@/api/client';
import { errorMessage, toast } from '@/components/ui';
import { useActiveSociety } from '@/hooks/useSociety';
import { isAdmin } from '@/utils/roles';

/** Pick several photos → presign/PUT each → register them in the gallery (members' go to moderation). */
export function useGalleryUpload(societyId?: string, eventId?: string) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { role } = useActiveSociety();
  const [loading, setLoading] = useState(false);

  const pick = async () => {
    if (!societyId) return;
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) return;
    const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsMultipleSelection: true, selectionLimit: 10, quality: 0.8 });
    if (res.canceled || !res.assets.length) return;
    setLoading(true);
    try {
      const ids: string[] = [];
      for (const a of res.assets) ids.push(await uploadImage(societyId, 'gallery', a.uri, a.mimeType));
      await post(`/societies/${societyId}/gallery`, { event_id: eventId ?? null, upload_ids: ids });
      toast(isAdmin(role) ? t('gallery.uploadedAdmin') : t('gallery.uploadedMember'), 'success');
      await qc.invalidateQueries({ queryKey: ['gallery'] });
    } catch (e) {
      toast(errorMessage(e, t), 'danger');
    } finally {
      setLoading(false);
    }
  };
  return { pick, loading };
}
