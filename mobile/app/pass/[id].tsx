import React, { useMemo, useRef } from 'react';
import { Dimensions, FlatList, View } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import QRCode from 'react-native-qrcode-svg';
import { useTranslation } from 'react-i18next';
import { Badge, Banner, ErrorState, Ionicons, LoadingView, Row, T } from '@/components/ui';
import { useMyPasses } from '@/hooks/usePasses';
import type { PassT } from '@/api/types';
import { colors, radius, shadow, space } from '@/theme';
import { formatDateTime, formatDay } from '@/utils/dates';

const W = Dimensions.get('window').width;

function PassCard({ pass, index, total }: { pass: PassT; index: number; total: number }) {
  const { t, i18n } = useTranslation();
  const revoked = pass.status === 'revoked';
  return (
    <View style={{ width: W, padding: space.lg }}>
      <View style={{ backgroundColor: colors.card, borderRadius: radius.xl, overflow: 'hidden', ...shadow }}>
        <View style={{ backgroundColor: colors.primary, padding: space.lg, gap: 2 }}>
          <T variant="caption" color="#C7D2FE">{pass.event.society_name}</T>
          <T variant="title" color="#fff" numberOfLines={2}>{pass.event.title}</T>
          <T variant="caption" color="#E0E7FF">{formatDateTime(pass.event.starts_at, i18n.language)}{pass.event.venue ? ` · ${pass.event.venue}` : ''}</T>
        </View>
        <View style={{ alignItems: 'center', padding: space.xl, gap: space.md, opacity: revoked ? 0.25 : 1 }}>
          <View style={{ padding: 12, backgroundColor: '#fff', borderRadius: radius.md, borderWidth: 1, borderColor: colors.border }}>
            <QRCode value={pass.qr_token} size={Math.min(W - 140, 260)} ecl="M" />
          </View>
          <T variant="caption" color={colors.muted}>{t('passes.showQr')}</T>
        </View>
        {revoked && <View style={{ position: 'absolute', top: 160, alignSelf: 'center' }}><Badge tone="danger" text={t('passes.revoked')} /></View>}
        <View style={{ borderTopWidth: 1, borderStyle: 'dashed', borderColor: colors.border, padding: space.lg, gap: space.sm }}>
          <Row style={{ justifyContent: 'space-between' }}>
            <View style={{ flex: 1 }}><T variant="caption" color={colors.muted}>{t('passes.holder')}</T><T variant="heading">{pass.holder_name}</T></View>
            <Badge tone={pass.holder_type === 'guest' ? 'info' : 'primary'} text={pass.holder_type === 'guest' ? t('passes.guest') : pass.tier_name} />
          </Row>
          <Row style={{ justifyContent: 'space-between' }}>
            <View style={{ flex: 1 }}><T variant="caption" color={colors.muted}>{t('passes.tier')}</T><T>{pass.tier_name}</T></View>
            {total > 1 && <T variant="caption" color={colors.muted}>{t('passes.ticketOf', { i: index + 1, n: total })}</T>}
          </Row>
          <T variant="caption" color={colors.muted}>
            {pass.valid_days === 'all' || !pass.valid_dates.length ? t('passes.validAllDays') : t('passes.validOnDays', { days: pass.valid_dates.map((d) => formatDay(d, i18n.language)).join(', ') })}
          </T>
          {pass.scanned_dates.length > 0 && (
            <Row gap={6}><Ionicons name="checkmark-circle" size={16} color={colors.success} />
              <T variant="caption" color={colors.success}>{t('passes.scannedOn', { date: pass.scanned_dates.map((d) => formatDay(d, i18n.language)).join(', ') })}</T></Row>
          )}
        </View>
      </View>
    </View>
  );
}

/** Full-screen QR. Swipe between the passes of the same order. Reads the on-device cached list, so it works offline. */
export default function PassDetail() {
  const { t } = useTranslation();
  const { id } = useLocalSearchParams<{ id: string }>();
  const q = useMyPasses();
  const ref = useRef<FlatList>(null);
  const { siblings, start } = useMemo(() => {
    const all = q.data?.passes ?? [];
    const me = all.find((p) => p.id === id);
    const sib = me ? all.filter((p) => p.order_id === me.order_id) : [];
    return { siblings: sib, start: Math.max(0, sib.findIndex((p) => p.id === id)) };
  }, [q.data, id]);

  if (q.isLoading) return <LoadingView />;
  if (!siblings.length) return <ErrorState error={q.error ?? new Error('not found')} onRetry={q.refetch} />;
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      {q.data?.offline && <View style={{ padding: space.lg, paddingBottom: 0 }}><Banner tone="warning" icon="cloud-offline" text={t('passes.offlineBanner')} /></View>}
      <FlatList
        ref={ref} data={siblings} horizontal pagingEnabled showsHorizontalScrollIndicator={false} keyExtractor={(p) => p.id}
        initialScrollIndex={start} getItemLayout={(_, i) => ({ length: W, offset: W * i, index: i })}
        renderItem={({ item, index }) => <PassCard pass={item} index={index} total={siblings.length} />}
      />
      <T variant="caption" color={colors.faint} style={{ textAlign: 'center', padding: space.lg }}>{t('passes.brightness')}</T>
    </View>
  );
}
