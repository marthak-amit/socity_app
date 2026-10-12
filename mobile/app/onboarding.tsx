import React from 'react';
import { View } from 'react-native';
import { Redirect, router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { Button, Card, Ionicons, Row, Screen, T } from '@/components/ui';
import { useActiveSociety } from '@/hooks/useSociety';
import { useAuth } from '@/store/auth';
import { colors, space } from '@/theme';

export default function Onboarding() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { add } = useLocalSearchParams<{ add?: string }>();
  const { pending, societyId, refetch, isLoading } = useActiveSociety();
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  if (societyId && !add) return <Redirect href="/(tabs)" />;

  return (
    <Screen edges={['top', 'bottom', 'left', 'right']} refreshing={isLoading} onRefresh={() => refetch()}>
      <T variant="display" style={{ marginTop: space.xl }}>{t('onboarding.title', { name: user?.name ? `, ${user.name.split(' ')[0]}` : '' })}</T>
      <T color={colors.muted}>{t('onboarding.subtitle')}</T>

      {pending.map((m) => (
        <Card key={m.id} style={{ backgroundColor: colors.warningSoft, borderColor: colors.warning }}>
          <Row><Ionicons name="time" size={22} color={colors.warning} /><T variant="heading">{t('onboarding.pendingTitle')}</T></Row>
          <T color={colors.text} style={{ marginTop: 4 }}>{t('onboarding.pendingBody', { name: m.society.name })}</T>
          <Button title={t('onboarding.checkStatus')} variant="secondary" size="sm" style={{ marginTop: space.md, alignSelf: 'flex-start' }}
            onPress={() => { void qc.invalidateQueries({ queryKey: ['me'] }); void refetch(); }} />
        </Card>
      ))}

      <Card onPress={() => router.push('/join')}>
        <Row gap={space.md}>
          <View style={{ width: 48, height: 48, borderRadius: 14, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="enter-outline" size={26} color={colors.primary} />
          </View>
          <View style={{ flex: 1 }}>
            <T variant="heading">{t('onboarding.join')}</T>
            <T variant="caption" color={colors.muted}>{t('onboarding.joinSub')}</T>
          </View>
          <Ionicons name="chevron-forward" size={20} color={colors.faint} />
        </Row>
      </Card>
      <Card onPress={() => router.push('/create-society')}>
        <Row gap={space.md}>
          <View style={{ width: 48, height: 48, borderRadius: 14, backgroundColor: colors.successSoft, alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="business-outline" size={26} color={colors.success} />
          </View>
          <View style={{ flex: 1 }}>
            <T variant="heading">{t('onboarding.create')}</T>
            <T variant="caption" color={colors.muted}>{t('onboarding.createSub')}</T>
          </View>
          <Ionicons name="chevron-forward" size={20} color={colors.faint} />
        </Row>
      </Card>
      {societyId ? <Button title={t('common.back')} variant="ghost" onPress={() => router.back()} /> : <Button title={t('onboarding.signOut')} variant="ghost" onPress={() => void logout()} />}
    </Screen>
  );
}
