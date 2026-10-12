import React, { useEffect, useState } from 'react';
import { Pressable, View } from 'react-native';
import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { del, patch, uploadImage } from '@/api/client';
import type { Society } from '@/api/types';
import { Banner, Button, Card, ErrorState, Input, Ionicons, LoadingView, Screen, SectionTitle, T, confirm, errorMessage, toast } from '@/components/ui';
import { useActiveSociety, useSocietyDetail } from '@/hooks/useSociety';
import { useAuth } from '@/store/auth';
import { colors, space } from '@/theme';
import { isValidUpiId } from '@/utils/validation';

export default function SocietySettings() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { societyId, role } = useActiveSociety();
  const setActive = useAuth((s) => s.setActiveSociety);
  const q = useSocietyDetail(societyId);
  const s = q.data;
  const [f, setF] = useState({ name: '', city: '', address: '', upi_id: '', upi_name: '' });
  const [logo, setLogo] = useState<{ uri: string; mime?: string | null } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmName, setConfirmName] = useState('');

  useEffect(() => { if (s) setF({ name: s.name, city: s.city, address: s.address ?? '', upi_id: s.upi_id ?? '', upi_name: s.upi_name ?? '' }); }, [s?.id, s?.upi_id]); // eslint-disable-line react-hooks/exhaustive-deps
  if (q.isLoading) return <LoadingView />;
  if (q.isError || !s) return <ErrorState error={q.error} onRetry={q.refetch} />;

  const pickLogo = async () => {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) return;
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.8, allowsEditing: true, aspect: [1, 1] });
    if (!r.canceled) setLogo({ uri: r.assets[0].uri, mime: r.assets[0].mimeType });
  };

  const save = async () => {
    if (f.upi_id && !isValidUpiId(f.upi_id)) return setError(t('createSociety.invalidUpi'));
    setBusy(true);
    setError(null);
    try {
      const logoId = logo ? await uploadImage(s.id, 'logo', logo.uri, logo.mime) : null;
      const updated = await patch<Society>(`/societies/${s.id}`, { name: f.name.trim(), city: f.city.trim(), address: f.address.trim() || null, upi_id: f.upi_id.trim(), upi_name: f.upi_name.trim() || null, logo_upload_id: logoId });
      qc.setQueryData(['society', s.id], updated);
      await qc.invalidateQueries({ queryKey: ['me'] });
      setLogo(null);
      toast(t('settings.saved'), 'success');
    } catch (e) {
      setError(errorMessage(e, t));
    } finally {
      setBusy(false);
    }
  };

  const deleteSociety = async () => {
    if (!(await confirm(t('manage.deleteSociety'), t('manage.deleteWarn'), t('common.delete'), true))) return;
    try {
      await del(`/societies/${s.id}`, { confirm_name: confirmName.trim() });
      await setActive(null);
      await qc.invalidateQueries({ queryKey: ['me'] });
      toast(t('manage.deleted'));
      router.replace('/');
    } catch (e) {
      toast(errorMessage(e, t), 'danger');
    }
  };

  return (
    <Screen>
      <Pressable onPress={pickLogo} style={{ alignSelf: 'center' }}>
        <View style={{ width: 96, height: 96, borderRadius: 24, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
          {logo || s.logo_url ? <Image source={{ uri: logo?.uri ?? s.logo_url ?? undefined }} style={{ width: 96, height: 96 }} /> : <Ionicons name="business" size={40} color={colors.primary} />}
        </View>
        <T variant="caption" color={colors.primary} style={{ textAlign: 'center', marginTop: 4 }}>{t('settings.logo')}</T>
      </Pressable>
      <Input label={t('settings.societyName')} value={f.name} onChangeText={(v) => setF({ ...f, name: v })} />
      <Input label={t('createSociety.city')} value={f.city} onChangeText={(v) => setF({ ...f, city: v })} />
      <Input label={t('createSociety.address')} value={f.address} onChangeText={(v) => setF({ ...f, address: v })} multiline />
      <SectionTitle>UPI</SectionTitle>
      <Input label={t('createSociety.upiId')} value={f.upi_id} onChangeText={(v) => setF({ ...f, upi_id: v })} autoCapitalize="none" autoCorrect={false} helper={t('createSociety.upiHelp')} />
      <Input label={t('createSociety.upiName')} value={f.upi_name} onChangeText={(v) => setF({ ...f, upi_name: v })} />
      {error ? <Banner tone="danger" text={error} /> : null}
      <Button title={t('common.save')} onPress={save} loading={busy} />

      {role === 'owner' && (
        <>
          <SectionTitle>{t('manage.dangerZone')}</SectionTitle>
          <Card style={{ borderColor: colors.danger, gap: space.sm }}>
            <T variant="caption" color={colors.muted}>{t('manage.deleteWarn')}</T>
            <Input label={t('manage.typeName')} value={confirmName} onChangeText={setConfirmName} placeholder={s.name} />
            <Button title={t('manage.deleteSociety')} variant="danger" disabled={confirmName.trim() !== s.name} onPress={deleteSociety} />
          </Card>
        </>
      )}
    </Screen>
  );
}
