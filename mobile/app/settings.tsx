import React from 'react';
import { router } from 'expo-router';
import Constants from 'expo-constants';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { patch, post } from '@/api/client';
import type { Me } from '@/api/types';
import { Avatar, Button, Card, Chip, Input, Row, Screen, SectionTitle, T, confirm, toast } from '@/components/ui';
import { LANGUAGES } from '@/i18n';
import { registerForPush } from '@/hooks/usePush';
import { useActiveSociety } from '@/hooks/useSociety';
import { useAuth } from '@/store/auth';
import { colors, space } from '@/theme';

export default function Settings() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const { user, logout, setUser, setLocale } = useAuth();
  const { societyId, role } = useActiveSociety();
  const [name, setName] = React.useState(user?.name ?? '');

  const saveName = async () => {
    if (name.trim().length < 2 || name.trim() === user?.name) return;
    const me = await patch<Me>('/me', { name: name.trim() });
    await setUser(me.user);
    qc.setQueryData(['me'], me);
    toast(t('settings.saved'), 'success');
  };
  const changeLang = async (code: string) => {
    await i18n.changeLanguage(code);
    await setLocale(code);
    try { await patch('/me', { locale: code }); } catch { /* offline: local choice still applies */ }
  };
  const signOut = async () => {
    if (!(await confirm(t('settings.signOut'), t('settings.signOutConfirm'), t('settings.signOut'), true))) return;
    qc.clear();
    await logout();
  };
  const leave = async () => {
    if (!(await confirm(t('manage.leave'), t('manage.leaveConfirm'), t('manage.leave'), true))) return;
    await post(`/societies/${societyId}/leave`);
    await useAuth.getState().setActiveSociety(null);
    await qc.invalidateQueries({ queryKey: ['me'] });
    router.replace('/');
  };

  return (
    <Screen>
      <Card>
        <Row gap={space.md}><Avatar name={user?.name} size={52} /><T variant="heading">{user?.name}</T></Row>
        <T variant="caption" color={colors.muted} style={{ marginTop: 6 }}>{t('settings.phone')}: {user?.phone}</T>
      </Card>
      <Input label={t('settings.name')} value={name} onChangeText={setName} onBlur={saveName} onSubmitEditing={saveName} autoCapitalize="words" />
      <SectionTitle>{t('settings.language')}</SectionTitle>
      <Row>{LANGUAGES.map((l) => <Chip key={l.code} label={l.label} selected={i18n.language === l.code} onPress={() => changeLang(l.code)} />)}</Row>
      <SectionTitle>{t('settings.notifications')}</SectionTitle>
      <Button title={t('settings.pushOff')} icon="notifications-outline" variant="secondary" onPress={async () => toast((await registerForPush()) ? t('settings.pushOn') : t('common.error'))} />
      {societyId && role && role !== 'owner' && <Button title={t('manage.leave')} variant="ghost" onPress={leave} />}
      <Button title={t('settings.signOut')} variant="danger" icon="log-out-outline" onPress={signOut} />
      <T variant="caption" color={colors.faint} style={{ textAlign: 'center' }}>{t('settings.version', { v: Constants.expoConfig?.version ?? '0.1.0' })}</T>
    </Screen>
  );
}
