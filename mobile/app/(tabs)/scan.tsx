import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Pressable, ScrollView, View } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as Crypto from 'expo-crypto';
import * as Haptics from 'expo-haptics';
import { useFocusEffect } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { post } from '@/api/client';
import type { Counters, ScanResult } from '@/api/types';
import { Button, Chip, EmptyState, ErrorState, Ionicons, LoadingView, Row, T, errorMessage } from '@/components/ui';
import { useScanEvents } from '@/hooks/queries';
import { useActiveSociety } from '@/hooks/useSociety';
import { colors, radius, space } from '@/theme';
import { formatTime } from '@/utils/dates';

type HistoryRow = { key: string; ok: boolean; title: string; sub: string; at: string };

export default function Scan() {
  const { t, i18n } = useTranslation();
  const { societyId } = useActiveSociety();
  const events = useScanEvents(societyId);
  const [permission, requestPermission] = useCameraPermissions();
  const [eventId, setEventId] = useState<string | null>(null);
  const [focused, setFocused] = useState(true);
  const [torch, setTorch] = useState(false);
  const [result, setResult] = useState<ScanResult | null>(null);
  const [netError, setNetError] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [counters, setCounters] = useState<Counters | null>(null);
  const busy = useRef(false);
  const last = useRef<{ token: string; at: number } | null>(null);
  const dismissTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useFocusEffect(useCallback(() => { setFocused(true); return () => { setFocused(false); setTorch(false); }; }, []));
  const list = events.data ?? [];
  const current = list.find((e) => e.event_id === eventId) ?? list[0];
  useEffect(() => { if (!eventId && list[0]) setEventId(list[0].event_id); }, [list, eventId]);
  useEffect(() => { setCounters(current?.counters ?? null); }, [current?.event_id, current?.counters.scanned_today, current?.counters.sold]); // eslint-disable-line react-hooks/exhaustive-deps

  const dismiss = useCallback(() => {
    if (dismissTimer.current) clearTimeout(dismissTimer.current);
    setResult(null);
    setNetError(null);
    busy.current = false;
  }, []);

  const onScan = async ({ data }: { data: string }) => {
    if (busy.current || !current || !societyId) return;
    const nowMs = Date.now();
    if (last.current && last.current.token === data && nowMs - last.current.at < 3000) return; // camera re-reads the same code
    last.current = { token: data, at: nowMs };
    busy.current = true;
    try {
      const r = await post<ScanResult>(`/societies/${societyId}/events/${current.event_id}/scan`, { qr_token: data, client_ref: Crypto.randomUUID() });
      setResult(r);
      setCounters(r.counters);
      void Haptics.notificationAsync(r.ok ? Haptics.NotificationFeedbackType.Success : Haptics.NotificationFeedbackType.Error);
      setHistory((h) => [{ key: Crypto.randomUUID(), ok: r.ok, title: r.holder_name ?? t(`scan.result.${r.result}`), sub: r.tier_name ?? r.message, at: new Date().toISOString() }, ...h].slice(0, 15));
      dismissTimer.current = setTimeout(dismiss, r.ok ? 2200 : 4500);
    } catch (e) {
      setNetError(errorMessage(e, t));
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      last.current = null; // allow immediate retry of the same code
      dismissTimer.current = setTimeout(dismiss, 3500);
    }
  };

  if (events.isLoading) return <LoadingView />;
  if (events.isError) return <ErrorState error={events.error} onRetry={events.refetch} />;
  if (!list.length) return <EmptyState icon="qr-code-outline" title={t('scan.noEvents')} subtitle={t('scan.noEventsSub')} />;
  if (!permission?.granted) {
    return <EmptyState icon="camera-outline" title={t('scan.permission')} action={<Button title={t('scan.grant')} onPress={requestPermission} />} />;
  }

  const green = result?.ok;
  return (
    <View style={{ flex: 1, backgroundColor: '#000' }}>
      {focused && <CameraView style={{ flex: 1 }} facing="back" enableTorch={torch} barcodeScannerSettings={{ barcodeTypes: ['qr'] }} onBarcodeScanned={onScan} />}

      <View style={{ position: 'absolute', top: 0, left: 0, right: 0, backgroundColor: 'rgba(17,24,39,0.85)', padding: space.md, gap: space.sm }}>
        {list.length > 1 && (
          <ScrollView horizontal showsHorizontalScrollIndicator={false}>
            <Row>{list.map((e) => <Chip key={e.event_id} label={e.title} selected={e.event_id === current?.event_id} onPress={() => setEventId(e.event_id)} />)}</Row>
          </ScrollView>
        )}
        <Row style={{ justifyContent: 'space-between' }}>
          <View>
            <T color="#fff" variant="heading" numberOfLines={1}>{current?.title}</T>
            <T color="#9CA3AF" variant="caption">{current?.day ? '' : t('scan.notEventDay')}</T>
          </View>
          <Pressable onPress={() => setTorch((v) => !v)} accessibilityLabel={t('scan.torch')} hitSlop={10}>
            <Ionicons name={torch ? 'flash' : 'flash-outline'} size={26} color="#fff" />
          </Pressable>
        </Row>
        {counters && (
          <Row gap={space.lg}>
            <View><T color="#34D399" variant="title">{counters.scanned_today}</T><T color="#9CA3AF" variant="caption">{t('scan.scanned')} {t('scan.today')}</T></View>
            <View><T color="#fff" variant="title">{counters.expected_today}</T><T color="#9CA3AF" variant="caption">{t('scan.expected')}</T></View>
            <View><T color="#fff" variant="title">{counters.sold}</T><T color="#9CA3AF" variant="caption">{t('scan.sold')}</T></View>
          </Row>
        )}
      </View>

      {!result && !netError && (
        <View pointerEvents="none" style={{ position: 'absolute', top: '32%', alignSelf: 'center', width: 240, height: 240, borderWidth: 3, borderColor: 'rgba(255,255,255,0.85)', borderRadius: radius.xl }} />
      )}

      {history.length > 0 && !result && (
        <View style={{ position: 'absolute', bottom: 0, left: 0, right: 0, backgroundColor: 'rgba(17,24,39,0.85)', padding: space.md, gap: 6, maxHeight: 180 }}>
          <T color="#9CA3AF" variant="caption">{t('scan.recent')}</T>
          {history.slice(0, 3).map((h) => (
            <Row key={h.key} gap={8}>
              <Ionicons name={h.ok ? 'checkmark-circle' : 'close-circle'} size={18} color={h.ok ? '#34D399' : '#F87171'} />
              <T color="#fff" variant="label" style={{ flex: 1 }} numberOfLines={1}>{h.title} · {h.sub}</T>
              <T color="#9CA3AF" variant="caption">{formatTime(h.at, i18n.language)}</T>
            </Row>
          ))}
        </View>
      )}

      {(result || netError) && (
        <Pressable onPress={dismiss} style={{ ...absoluteFill, backgroundColor: netError ? '#374151' : green ? '#16A34A' : '#DC2626', alignItems: 'center', justifyContent: 'center', padding: space.xl, gap: space.md }}>
          <Ionicons name={netError ? 'cloud-offline' : green ? 'checkmark-circle' : 'close-circle'} size={110} color="#fff" />
          <T color="#fff" variant="display" style={{ textAlign: 'center' }}>{netError ? t('common.error') : green ? t('scan.allowed') : t('scan.denied')}</T>
          {netError ? <T color="#fff" style={{ textAlign: 'center' }}>{netError}</T> : (
            <>
              {result?.holder_name && <T color="#fff" variant="title" style={{ textAlign: 'center' }}>{result.holder_name}</T>}
              {result?.tier_name && <T color="#fff" variant="heading">{result.tier_name}{result.holder_type === 'guest' ? ` · ${t('passes.guest')}` : ''}</T>}
              <T color="#fff" style={{ textAlign: 'center' }}>{t(`scan.result.${result?.result ?? 'invalid_token'}`, { defaultValue: result?.message })}</T>
              {result?.result === 'already_scanned' && result.scanned_at && (
                <T color="#fff" variant="caption">{t('scan.scannedAt', { time: formatTime(result.scanned_at, i18n.language) })}{result.scanned_by ? ` ${t('scan.by', { name: result.scanned_by })}` : ''}</T>
              )}
            </>
          )}
          <T color="rgba(255,255,255,0.8)" variant="caption" style={{ marginTop: space.lg }}>{t('scan.tapContinue')}</T>
        </Pressable>
      )}
    </View>
  );
}

const absoluteFill = { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 } as const;
