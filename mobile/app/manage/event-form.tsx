import React, { useEffect, useMemo, useState } from 'react';
import { Pressable, Switch, View } from 'react-native';
import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError, del, patch, post, uploadImage } from '@/api/client';
import type { EventT, Tier } from '@/api/types';
import { Banner, Button, Card, Chip, ErrorState, Input, Ionicons, LoadingView, Row, Screen, SectionTitle, T, errorMessage, toast } from '@/components/ui';
import { DateTimeField } from '@/components/DateTimeField';
import { useEvent } from '@/hooks/queries';
import { useActiveSociety } from '@/hooks/useSociety';
import { colors, space } from '@/theme';
import { formatDay, toDayString } from '@/utils/dates';

type TierDraft = {
  key: string; id?: string; name: string; price: string; capacity: string; per_user_limit: string; allow_guests: boolean;
  valid_days: 'all' | 'specific'; day_dates: string[]; description?: string;
};
const blankTier = (): TierDraft => ({ key: String(Math.random()), name: '', price: '', capacity: '100', per_user_limit: '4', allow_guests: true, valid_days: 'all', day_dates: [] });

function daysBetween(start: Date, end: Date): string[] {
  const out: string[] = [];
  const d = new Date(start.getFullYear(), start.getMonth(), start.getDate());
  const last = new Date(end.getFullYear(), end.getMonth(), end.getDate());
  while (d <= last && out.length < 31) { out.push(toDayString(d)); d.setDate(d.getDate() + 1); }
  return out;
}

export default function EventForm() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const { id } = useLocalSearchParams<{ id?: string }>();
  const { societyId } = useActiveSociety();
  const existing = useEvent(societyId, id);
  const editing = !!id;

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [venue, setVenue] = useState('');
  const [starts, setStarts] = useState<Date | null>(null);
  const [ends, setEnds] = useState<Date | null>(null);
  const [deadline, setDeadline] = useState<Date | null>(null);
  const [isPaid, setIsPaid] = useState(true);
  const [banner, setBanner] = useState<{ uri: string; mime?: string | null } | null>(null);
  const [tiers, setTiers] = useState<TierDraft[]>([blankTier()]);
  const [removed, setRemoved] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loaded = existing.data;
  useEffect(() => {
    if (!loaded) return;
    setTitle(loaded.title); setDescription(loaded.description ?? ''); setVenue(loaded.venue ?? '');
    setStarts(new Date(loaded.starts_at)); setEnds(new Date(loaded.ends_at));
    setDeadline(loaded.booking_deadline ? new Date(loaded.booking_deadline) : null); setIsPaid(loaded.is_paid);
    const dateOf = (dayId: string) => loaded.days.find((d) => d.id === dayId)?.date ?? '';
    setTiers(loaded.tiers.map((x: Tier) => ({
      key: x.id, id: x.id, name: x.name, price: String(x.price), capacity: String(x.capacity), per_user_limit: String(x.per_user_limit),
      allow_guests: x.allow_guests, valid_days: x.valid_days, day_dates: x.day_ids.map(dateOf).filter(Boolean), description: x.description ?? undefined,
    })));
  }, [loaded?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const dayOptions = useMemo(() => (editing && loaded ? loaded.days.map((d) => d.date) : starts && ends ? daysBetween(starts, ends) : []), [editing, loaded, starts, ends]);

  if (editing && existing.isLoading) return <LoadingView />;
  if (editing && existing.isError) return <ErrorState error={existing.error} onRetry={existing.refetch} />;

  const updateTier = (key: string, patchT: Partial<TierDraft>) => setTiers((p) => p.map((x) => (x.key === key ? { ...x, ...patchT } : x)));
  const pickBanner = async () => {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) return;
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.8, allowsEditing: true, aspect: [16, 9] });
    if (!r.canceled) setBanner({ uri: r.assets[0].uri, mime: r.assets[0].mimeType });
  };

  const tierBody = (x: TierDraft) => ({
    name: x.name.trim(), description: x.description ?? null, price: isPaid ? Number(x.price || 0) : 0, capacity: Number(x.capacity), per_user_limit: Number(x.per_user_limit || 1),
    allow_guests: x.allow_guests, valid_days: x.valid_days, day_dates: x.valid_days === 'specific' ? x.day_dates : [],
  });

  const save = async () => {
    if (title.trim().length < 2) return setError(t('eventForm.needTitle'));
    if (!starts || !ends || ends < starts) return setError(t('eventForm.badDates'));
    if (!tiers.length) return setError(t('eventForm.needTier'));
    if (tiers.some((x) => !x.name.trim() || !(Number(x.capacity) >= 0) || x.capacity === '' || (isPaid && x.price !== '' && !(Number(x.price) >= 0)) || (x.valid_days === 'specific' && !x.day_dates.length))) return setError(t('eventForm.tierInvalid'));
    setBusy(true);
    setError(null);
    try {
      const bannerId = banner ? await uploadImage(societyId!, 'banner', banner.uri, banner.mime) : null;
      let eventId = id;
      if (!editing) {
        const created = await post<EventT>(`/societies/${societyId}/events`, {
          title: title.trim(), description: description.trim() || null, venue: venue.trim() || null, starts_at: starts.toISOString(), ends_at: ends.toISOString(),
          booking_deadline: deadline?.toISOString() ?? null, is_paid: isPaid, banner_upload_id: bannerId, tiers: tiers.map(tierBody),
        });
        eventId = created.id;
      } else {
        await patch(`/societies/${societyId}/events/${id}`, {
          title: title.trim(), description: description.trim() || null, venue: venue.trim() || null, starts_at: starts.toISOString(), ends_at: ends.toISOString(),
          booking_deadline: deadline?.toISOString(), clear_booking_deadline: !deadline, banner_upload_id: bannerId,
        });
        for (const rid of removed) await del(`/societies/${societyId}/events/${id}/tiers/${rid}`);
        for (const x of tiers) {
          if (x.id) await patch(`/societies/${societyId}/events/${id}/tiers/${x.id}`, tierBody(x));
          else await post(`/societies/${societyId}/events/${id}/tiers`, tierBody(x));
        }
      }
      await Promise.all([qc.invalidateQueries({ queryKey: ['events'] }), qc.invalidateQueries({ queryKey: ['event'] })]);
      toast(t('eventForm.saved'), 'success');
      if (editing) router.back(); else router.replace(`/manage/event/${eventId}`);
    } catch (e) {
      setError(e instanceof ApiError && e.code === 'validation_error' ? t('eventForm.tierInvalid') : errorMessage(e, t));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen>
      <Input label={t('eventForm.title')} value={title} onChangeText={setTitle} maxLength={160} autoCapitalize="words" />
      <Input label={t('eventForm.description')} value={description} onChangeText={setDescription} multiline maxLength={5000} />
      <Input label={t('eventForm.venue')} value={venue} onChangeText={setVenue} maxLength={200} />
      <DateTimeField label={t('eventForm.starts')} value={starts} onChange={(d) => { setStarts(d); if (!ends || ends < d) setEnds(new Date(d.getTime() + 3 * 3600_000)); }} />
      <DateTimeField label={t('eventForm.ends')} value={ends} onChange={setEnds} />
      <DateTimeField label={t('eventForm.deadline')} value={deadline} onChange={setDeadline} onClear={() => setDeadline(null)} placeholder={t('eventForm.noDeadline')} />
      {dayOptions.length > 1 && <Banner tone="info" icon="calendar" text={`${dayOptions.length} ${t('event.days')} — ${t('eventForm.daysHelp')}`} />}

      <T variant="label" color={colors.muted}>{t('eventForm.banner')}</T>
      <Pressable onPress={pickBanner} style={{ height: 150, borderRadius: 16, backgroundColor: colors.primarySoft, overflow: 'hidden', alignItems: 'center', justifyContent: 'center' }}>
        {banner || loaded?.banner_url ? <Image source={{ uri: banner?.uri ?? loaded?.banner_url ?? undefined }} style={{ width: '100%', height: '100%' }} contentFit="cover" /> : (
          <><Ionicons name="image-outline" size={32} color={colors.primary} /><T color={colors.primary}>{t('eventForm.pickBanner')}</T></>
        )}
      </Pressable>

      <Card>
        <Row style={{ justifyContent: 'space-between' }}>
          <View style={{ flex: 1 }}><T variant="heading">{t('eventForm.paid')}</T><T variant="caption" color={colors.muted}>{t('eventForm.paidHelp')}</T></View>
          <Switch value={isPaid} onValueChange={setIsPaid} trackColor={{ true: colors.primary }} disabled={editing && !!loaded && loaded.tiers.some((x) => x.sold + x.pending > 0)} />
        </Row>
      </Card>

      <SectionTitle>{t('eventForm.tiers')}</SectionTitle>
      {tiers.map((x, i) => (
        <Card key={x.key} style={{ gap: space.sm }}>
          <Row style={{ justifyContent: 'space-between' }}>
            <T variant="label" color={colors.muted}>#{i + 1}</T>
            {tiers.length > 1 && (
              <Pressable hitSlop={8} onPress={() => { if (x.id) setRemoved((r) => [...r, x.id!]); setTiers((p) => p.filter((y) => y.key !== x.key)); }}><Ionicons name="trash-outline" size={20} color={colors.danger} /></Pressable>
            )}
          </Row>
          <Input label={t('eventForm.tierName')} value={x.name} onChangeText={(v) => updateTier(x.key, { name: v })} maxLength={80} />
          <Row gap={space.sm}>
            {isPaid && <View style={{ flex: 1 }}><Input label={t('eventForm.price')} value={x.price} onChangeText={(v) => updateTier(x.key, { price: v.replace(/\D/g, '') })} keyboardType="number-pad" placeholder="0" /></View>}
            <View style={{ flex: 1 }}><Input label={t('eventForm.capacity')} value={x.capacity} onChangeText={(v) => updateTier(x.key, { capacity: v.replace(/\D/g, '') })} keyboardType="number-pad" /></View>
            <View style={{ flex: 1 }}><Input label={t('eventForm.perUser')} value={x.per_user_limit} onChangeText={(v) => updateTier(x.key, { per_user_limit: v.replace(/\D/g, '') })} keyboardType="number-pad" /></View>
          </Row>
          <Row style={{ justifyContent: 'space-between' }}>
            <T>{t('eventForm.guests')}</T>
            <Switch value={x.allow_guests} onValueChange={(v) => updateTier(x.key, { allow_guests: v })} trackColor={{ true: colors.primary }} />
          </Row>
          {dayOptions.length > 1 && (
            <>
              <T variant="label" color={colors.muted}>{t('eventForm.validDays')}</T>
              <Row>
                <Chip label={t('eventForm.allDays')} selected={x.valid_days === 'all'} onPress={() => updateTier(x.key, { valid_days: 'all', day_dates: [] })} />
                <Chip label={t('eventForm.specificDays')} selected={x.valid_days === 'specific'} onPress={() => updateTier(x.key, { valid_days: 'specific' })} />
              </Row>
              {x.valid_days === 'specific' && (
                <Row style={{ flexWrap: 'wrap' }}>
                  {dayOptions.map((d) => (
                    <Chip key={d} label={formatDay(d, i18n.language)} selected={x.day_dates.includes(d)}
                      onPress={() => updateTier(x.key, { day_dates: x.day_dates.includes(d) ? x.day_dates.filter((y) => y !== d) : [...x.day_dates, d] })} />
                  ))}
                </Row>
              )}
            </>
          )}
        </Card>
      ))}
      <Button title={t('eventForm.addTier')} icon="add" variant="secondary" onPress={() => setTiers((p) => [...p, blankTier()])} />
      {error ? <Banner tone="danger" text={error} /> : null}
      <Button title={editing ? t('eventForm.saveChanges') : t('eventForm.saveDraft')} onPress={save} loading={busy} />
    </Screen>
  );
}
