import React, { useState } from 'react';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { post } from '@/api/client';
import type { Society } from '@/api/types';
import { Banner, Button, Input, Row, Screen, T, errorMessage, toast } from '@/components/ui';
import { useAuth } from '@/store/auth';
import { colors } from '@/theme';
import { isValidUpiId } from '@/utils/validation';

export default function CreateSociety() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const setActive = useAuth((s) => s.setActiveSociety);
  const [f, setF] = useState({ name: '', city: '', address: '', upi_id: '', upi_name: '', wing: '', flat_no: '' });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const set = (k: keyof typeof f) => (v: string) => setF((p) => ({ ...p, [k]: v }));

  const submit = async () => {
    if (f.name.trim().length < 2 || f.city.trim().length < 2) return setError(t('common.required'));
    if (f.upi_id && !isValidUpiId(f.upi_id)) return setError(t('createSociety.invalidUpi'));
    setLoading(true);
    setError(null);
    try {
      const s = await post<Society>('/societies', {
        name: f.name.trim(), city: f.city.trim(), address: f.address.trim() || null, upi_id: f.upi_id.trim() || null,
        upi_name: f.upi_name.trim() || null, wing: f.wing.trim() || null, flat_no: f.flat_no.trim() || null,
      });
      await qc.invalidateQueries({ queryKey: ['me'] });
      await setActive(s.id);
      toast(t('createSociety.created'), 'success');
      router.replace('/manage/invite');
    } catch (e) {
      setError(errorMessage(e, t));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Screen>
      <Input label={t('createSociety.name')} value={f.name} onChangeText={set('name')} autoCapitalize="words" />
      <Input label={t('createSociety.city')} value={f.city} onChangeText={set('city')} autoCapitalize="words" />
      <Input label={t('createSociety.address')} value={f.address} onChangeText={set('address')} multiline />
      <T variant="heading">UPI</T>
      <Input label={t('createSociety.upiId')} value={f.upi_id} onChangeText={set('upi_id')} autoCapitalize="none" autoCorrect={false} placeholder="society@okhdfc" helper={t('createSociety.upiHelp')} />
      <Input label={t('createSociety.upiName')} value={f.upi_name} onChangeText={set('upi_name')} />
      <Row gap={12}>
        <Input label={t('createSociety.wing')} value={f.wing} onChangeText={set('wing')} style={{ minWidth: 120 }} />
        <Input label={t('createSociety.flat')} value={f.flat_no} onChangeText={set('flat_no')} style={{ minWidth: 120 }} />
      </Row>
      {error ? <Banner tone="danger" text={error} /> : null}
      <Button title={t('createSociety.create')} onPress={submit} loading={loading} />
      <T variant="caption" color={colors.muted}> </T>
    </Screen>
  );
}
