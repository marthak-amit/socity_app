import React from 'react';
import { Share, View } from 'react-native';
import * as Clipboard from 'expo-clipboard';
import QRCode from 'react-native-qrcode-svg';
import { useTranslation } from 'react-i18next';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { get, post } from '@/api/client';
import type { Invite } from '@/api/types';
import { Button, Card, ErrorState, LoadingView, Screen, T, confirm, errorMessage, toast } from '@/components/ui';
import { useActiveSociety } from '@/hooks/useSociety';
import { colors, space } from '@/theme';

export default function InviteScreen() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { societyId, society } = useActiveSociety();
  const q = useQuery({ queryKey: ['invite', societyId], enabled: !!societyId, queryFn: () => get<Invite>(`/societies/${societyId}/invite`) });
  if (q.isLoading) return <LoadingView />;
  if (q.isError || !q.data) return <ErrorState error={q.error} onRetry={q.refetch} />;
  const inv = q.data;

  const rotate = async () => {
    if (!(await confirm(t('invite.rotate'), t('invite.rotateConfirm'), t('common.confirm'), true))) return;
    try {
      qc.setQueryData(['invite', societyId], await post<Invite>(`/societies/${societyId}/invite/rotate`));
      void qc.invalidateQueries({ queryKey: ['society'] });
    } catch (e) { toast(errorMessage(e, t), 'danger'); }
  };

  return (
    <Screen>
      <Card style={{ alignItems: 'center', gap: space.md, padding: space.xl }}>
        <T variant="heading">{society?.name}</T>
        <View style={{ padding: 12, backgroundColor: '#fff', borderRadius: 12, borderWidth: 1, borderColor: colors.border }}>
          <QRCode value={inv.deep_link} size={200} ecl="M" />
        </View>
        <T variant="caption" color={colors.muted}>{t('invite.scanHint')}</T>
        <T variant="caption" color={colors.muted}>{t('invite.code')}</T>
        <T variant="display" selectable style={{ letterSpacing: 4 }}>{inv.code}</T>
      </Card>
      <Button title={t('invite.share')} icon="share-social" onPress={() => Share.share({ message: inv.share_text })} />
      <Button title={t('common.copy')} icon="copy-outline" variant="secondary" onPress={async () => { await Clipboard.setStringAsync(inv.code); toast(t('invite.copied')); }} />
      <Button title={t('invite.rotate')} variant="ghost" onPress={rotate} />
    </Screen>
  );
}
