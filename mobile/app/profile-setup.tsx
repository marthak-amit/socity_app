import React, { useState } from 'react';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { patch } from '@/api/client';
import type { Me } from '@/api/types';
import { Button, Input, Screen, T, errorMessage } from '@/components/ui';
import { useAuth } from '@/store/auth';
import { colors } from '@/theme';

export default function ProfileSetup() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const setUser = useAuth((s) => s.setUser);
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const save = async () => {
    if (name.trim().length < 2) return setError(t('common.required'));
    setLoading(true);
    try {
      const me = await patch<Me>('/me', { name: name.trim() });
      await setUser(me.user);
      qc.setQueryData(['me'], me);
      router.replace('/');
    } catch (e) {
      setError(errorMessage(e, t));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Screen>
      <T variant="title" style={{ marginTop: 24 }}>{t('auth.yourName')}</T>
      <T color={colors.muted}>{t('auth.nameHelp')}</T>
      <Input value={name} onChangeText={setName} placeholder={t('auth.namePlaceholder')} autoFocus error={error} autoCapitalize="words" />
      <Button title={t('common.continue')} onPress={save} loading={loading} />
    </Screen>
  );
}
