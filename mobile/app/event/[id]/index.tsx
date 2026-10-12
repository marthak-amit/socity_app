import React from 'react';
import { View } from 'react-native';
import { Image } from 'expo-image';
import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { Badge, Banner, Button, Card, ErrorState, Ionicons, LoadingView, Row, Screen, SectionTitle, T } from '@/components/ui';
import { PhotoGrid } from '@/components/PhotoGrid';
import { flat, useEvent, useGallery } from '@/hooks/queries';
import { useActiveSociety } from '@/hooks/useSociety';
import { useGalleryUpload } from '@/hooks/useGalleryUpload';
import { colors, radius, space } from '@/theme';
import { formatDateTime, formatDay } from '@/utils/dates';
import { priceLabel } from '@/utils/money';
import { isAdmin } from '@/utils/roles';

export default function EventDetail() {
  const { t, i18n } = useTranslation();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { societyId, role } = useActiveSociety();
  const q = useEvent(societyId, id);
  const ev = q.data;
  const photos = useGallery(societyId, { event_id: id });
  const upload = useGalleryUpload(societyId, id);

  if (q.isLoading) return <LoadingView />;
  if (q.isError || !ev) return <ErrorState error={q.error ?? new Error(t('event.notFound'))} onRetry={q.refetch} />;

  const dayLabel = (dayIds: string[]) => ev.days.filter((d) => dayIds.includes(d.id)).map((d) => formatDay(d.date, i18n.language)).join(', ');
  const anyAvailable = ev.tiers.some((tier) => tier.remaining > 0);
  const canBook = ev.booking_open && anyAvailable;

  return (
    <View style={{ flex: 1 }}>
      <Screen padded={false} refreshing={q.isRefetching} onRefresh={() => { void q.refetch(); void photos.refetch(); }} style={{ paddingBottom: 120 }}>
        <View style={{ height: 200, backgroundColor: colors.primarySoft }}>
          {ev.banner_url ? <Image source={{ uri: ev.banner_url }} style={{ flex: 1 }} contentFit="cover" /> : (
            <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}><Ionicons name="sparkles" size={56} color={colors.primary} /></View>
          )}
        </View>
        <View style={{ padding: space.lg, gap: space.md }}>
          <Row style={{ flexWrap: 'wrap' }}>
            {ev.status === 'draft' && <Badge text={t('home.draft')} tone="warning" />}
            {ev.status === 'cancelled' && <Badge text={t('home.cancelledBadge')} tone="danger" />}
            {ev.status === 'closed' && <Badge text={t('home.closed')} tone="neutral" />}
            {ev.days.length > 1 && <Badge text={`${ev.days.length} ${t('event.days')}`} tone="primary" />}
          </Row>
          <T variant="title">{ev.title}</T>
          <Card>
            <Row gap={space.md}><Ionicons name="time-outline" size={20} color={colors.primary} />
              <View style={{ flex: 1 }}><T variant="caption" color={colors.muted}>{t('event.when')}</T>
                <T>{formatDateTime(ev.starts_at, i18n.language)}</T>
                <T variant="caption" color={colors.muted}>→ {formatDateTime(ev.ends_at, i18n.language)}</T></View></Row>
            {ev.venue ? <Row gap={space.md} style={{ marginTop: space.md }}><Ionicons name="location-outline" size={20} color={colors.primary} />
              <View style={{ flex: 1 }}><T variant="caption" color={colors.muted}>{t('event.venue')}</T><T>{ev.venue}</T></View></Row> : null}
            {ev.booking_deadline ? <Row gap={space.md} style={{ marginTop: space.md }}><Ionicons name="hourglass-outline" size={20} color={colors.warning} />
              <T>{t('event.deadline', { date: formatDateTime(ev.booking_deadline, i18n.language) })}</T></Row> : null}
          </Card>
          {ev.status === 'cancelled' && <Banner tone="danger" text={t('event.cancelled')} />}
          {ev.description ? (<><SectionTitle>{t('event.about')}</SectionTitle><T color={colors.text}>{ev.description}</T></>) : null}

          <SectionTitle>{t('event.passes')}</SectionTitle>
          {ev.tiers.map((tier) => (
            <Card key={tier.id} style={tier.remaining === 0 ? { opacity: 0.6 } : undefined}>
              <Row style={{ justifyContent: 'space-between' }}>
                <T variant="heading" style={{ flex: 1 }}>{tier.name}</T>
                <T variant="heading" color={colors.primary}>{priceLabel(tier.price)}</T>
              </Row>
              {tier.description ? <T variant="caption" color={colors.muted}>{tier.description}</T> : null}
              <Row style={{ flexWrap: 'wrap', marginTop: space.sm }}>
                {tier.remaining === 0 ? <Badge text={t('event.soldOut')} tone="danger" /> : <Badge text={t('event.left', { n: tier.remaining })} tone={tier.remaining <= 10 ? 'warning' : 'success'} />}
                <Badge text={tier.valid_days === 'all' ? t('event.allDays') : t('event.validOn', { days: dayLabel(tier.day_ids) })} tone="neutral" />
                {tier.allow_guests && <Badge text={t('event.guestsOk')} tone="info" />}
                <Badge text={t('event.maxPerUser', { n: tier.per_user_limit })} tone="neutral" />
              </Row>
            </Card>
          ))}

          {isAdmin(role) && (
            <Button title={t('event.manage')} icon="construct-outline" variant="secondary" onPress={() => router.push(`/manage/event/${ev.id}`)} />
          )}

          {ev.is_over || isAdmin(role) ? (
            <>
              <SectionTitle right={<Button title={t('event.addPhotos')} icon="add" size="sm" variant="secondary" onPress={upload.pick} loading={upload.loading} />}>{t('event.photos')}</SectionTitle>
              {flat(photos.data).length ? <PhotoGrid items={flat(photos.data)} /> : <T color={colors.muted}>{t('event.noPhotos')}</T>}
            </>
          ) : (
            <Banner tone="info" icon="images-outline" text={t('event.photosLocked')} />
          )}
        </View>
      </Screen>
      <View style={{ position: 'absolute', bottom: 0, left: 0, right: 0, padding: space.lg, backgroundColor: colors.card, borderTopWidth: 1, borderTopColor: colors.border }}>
        {canBook ? (
          <Button title={t('event.getPasses')} icon="ticket" onPress={() => router.push(`/event/${ev.id}/buy`)} />
        ) : (
          <Button title={ev.is_over ? t('event.eventOver') : !anyAvailable && ev.booking_open ? t('event.soldOut') : t('event.bookingClosed')} disabled variant="secondary" />
        )}
      </View>
      <View style={{ height: 0, borderRadius: radius.sm }} />
    </View>
  );
}
