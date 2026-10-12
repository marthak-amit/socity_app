import React from 'react';
import { View } from 'react-native';
import { Image } from 'expo-image';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import type { EventT } from '@/api/types';
import { Badge, Card, Ionicons, Row, T } from '@/components/ui';
import { colors, radius, space } from '@/theme';
import { formatDateRange, formatTime } from '@/utils/dates';
import { formatINR } from '@/utils/money';

export function minPrice(e: EventT): number | null {
  const prices = e.tiers.filter((t) => t.remaining > 0).map((t) => t.price);
  return prices.length ? Math.min(...prices) : null;
}

export function EventCard({ event, onPress }: { event: EventT; onPress?: () => void }) {
  const { t, i18n } = useTranslation();
  const price = minPrice(event);
  const soldOut = event.tiers.length > 0 && price === null;
  return (
    <Card style={{ padding: 0, overflow: 'hidden' }} onPress={onPress ?? (() => router.push(`/event/${event.id}`))}>
      <View style={{ height: 150, backgroundColor: colors.primarySoft }}>
        {event.banner_url ? (
          <Image source={{ uri: event.banner_url }} style={{ flex: 1 }} contentFit="cover" transition={150} />
        ) : (
          <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}><Ionicons name="sparkles" size={40} color={colors.primary} /></View>
        )}
        <View style={{ position: 'absolute', top: 10, left: 10, flexDirection: 'row', gap: 6 }}>
          {event.status === 'draft' && <Badge text={t('home.draft')} tone="warning" />}
          {event.status === 'cancelled' && <Badge text={t('home.cancelledBadge')} tone="danger" />}
          {event.status === 'closed' && <Badge text={t('home.closed')} tone="neutral" />}
          {soldOut && event.status === 'published' && <Badge text={t('home.soldOut')} tone="danger" />}
        </View>
      </View>
      <View style={{ padding: space.lg, gap: 6 }}>
        <T variant="heading" numberOfLines={2}>{event.title}</T>
        <Row gap={6}><Ionicons name="calendar-outline" size={15} color={colors.muted} />
          <T variant="caption" color={colors.muted}>{formatDateRange(event.starts_at, event.ends_at, i18n.language)} · {formatTime(event.starts_at, i18n.language)}</T></Row>
        {event.venue ? <Row gap={6}><Ionicons name="location-outline" size={15} color={colors.muted} /><T variant="caption" color={colors.muted} numberOfLines={1}>{event.venue}</T></Row> : null}
        {price !== null && (
          <View style={{ marginTop: 4, alignSelf: 'flex-start', backgroundColor: colors.primarySoft, borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 3 }}>
            <T variant="caption" color={colors.primary} bold>{price === 0 ? t('home.free') : t('home.from', { price: formatINR(price) })}</T>
          </View>
        )}
      </View>
    </Card>
  );
}
