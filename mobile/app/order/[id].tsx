import React, { useEffect, useState } from 'react';
import { Linking, View } from 'react-native';
import { Image } from 'expo-image';
import * as Clipboard from 'expo-clipboard';
import * as ImagePicker from 'expo-image-picker';
import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError, post, uploadImage } from '@/api/client';
import type { Order } from '@/api/types';
import { Badge, Banner, Button, Card, Divider, ErrorState, Input, Ionicons, LoadingView, Row, Screen, SectionTitle, T, confirm, errorMessage, toast } from '@/components/ui';
import { useOrder } from '@/hooks/queries';
import { useActiveSociety } from '@/hooks/useSociety';
import { colors, space } from '@/theme';
import { formatCountdown, formatDateTime } from '@/utils/dates';
import { formatINR } from '@/utils/money';
import { isValidUtr, sanitizeUtr } from '@/utils/validation';

export default function OrderScreen() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { societyId } = useActiveSociety();
  const q = useOrder(societyId, id);
  const order = q.data;
  const [shot, setShot] = useState<{ uri: string; mime?: string | null } | null>(null);
  const [utr, setUtr] = useState('');
  const [paid, setPaid] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(Date.now());

  useEffect(() => { const i = setInterval(() => setNow(Date.now()), 30_000); return () => clearInterval(i); }, []);
  useEffect(() => { if (order) { setUtr((u) => u || order.utr || ''); setPaid((p) => p || String(order.paid_amount ?? order.total_amount)); } }, [order?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  // keep status fresh while waiting for the admin
  useEffect(() => {
    if (order?.status !== 'pending') return;
    const i = setInterval(() => void q.refetch(), 20_000);
    return () => clearInterval(i);
  }, [order?.status, q]);

  if (q.isLoading) return <LoadingView />;
  if (q.isError || !order) return <ErrorState error={q.error} onRetry={q.refetch} />;

  const refresh = async (o?: Order) => {
    if (o) qc.setQueryData(['order', societyId, id], o);
    await Promise.all([qc.invalidateQueries({ queryKey: ['event'] }), qc.invalidateQueries({ queryKey: ['orders-mine'] }), qc.invalidateQueries({ queryKey: ['passes'] })]);
  };

  const payViaUpi = async () => {
    const uri = order.payment?.upi_uri;
    if (!uri) return;
    try {
      await Linking.openURL(uri);
    } catch {
      toast(t('order.noUpiApp'));
    }
  };

  const pickShot = async () => {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) return;
    const r = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.8 });
    if (!r.canceled) { setShot({ uri: r.assets[0].uri, mime: r.assets[0].mimeType }); setError(null); }
  };

  const submit = async () => {
    const hasUtr = utr.length > 0;
    if (hasUtr && !isValidUtr(utr)) return setError(t('order.invalidUtr'));
    if (!hasUtr && !shot && !order.has_screenshot) return setError(t('order.proofRequired'));
    setBusy(true);
    setError(null);
    try {
      const uploadId = shot ? await uploadImage(societyId!, 'screenshot', shot.uri, shot.mime) : null;
      const updated = await post<Order>(`/societies/${societyId}/orders/${order.id}/payment`, {
        screenshot_upload_id: uploadId, utr: hasUtr ? utr : null, paid_amount: paid ? Number(paid) : null,
      });
      setShot(null);
      toast(t('order.submitted'), 'success');
      await refresh(updated);
    } catch (e) {
      setError(errorMessage(e, t));
      if (e instanceof ApiError && e.code === 'order_expired') void q.refetch();
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    if (!(await confirm(t('order.cancelOrder'), t('order.cancelConfirm'), t('common.yes'), true))) return;
    try {
      await post(`/societies/${societyId}/orders/${order.id}/cancel`);
      await refresh();
      router.back();
    } catch (e) {
      toast(errorMessage(e, t), 'danger');
    }
  };

  const pending = order.status === 'pending';
  const submitted = !!order.payment_submitted_at;
  const expired = pending && !submitted && order.expires_at && new Date(order.expires_at).getTime() < now;
  const tone = order.status === 'approved' ? 'success' : order.status === 'pending' ? 'warning' : 'danger';

  return (
    <Screen refreshing={q.isRefetching} onRefresh={() => q.refetch()}>
      <Card>
        <Row style={{ justifyContent: 'space-between' }}>
          <View style={{ flex: 1 }}>
            <T variant="caption" color={colors.muted}>{t('order.title', { ref: order.ref_code })}</T>
            <T variant="heading">{order.event_title}</T>
          </View>
          <Badge tone={tone} text={order.status === 'pending' ? (submitted ? t('order.inReview') : t('order.awaitingPayment')) : t(`common.${order.status}`)} />
        </Row>
        <Divider />
        {order.items.map((it) => (
          <Row key={it.tier_id} style={{ justifyContent: 'space-between' }}>
            <T>{it.qty} × {it.tier_name}</T>
            <T>{formatINR(it.qty * it.unit_price)}</T>
          </Row>
        ))}
        <Divider />
        <Row style={{ justifyContent: 'space-between' }}><T variant="heading">{t('buy.total')}</T><T variant="heading" color={colors.primary}>{formatINR(order.total_amount)}</T></Row>
        <T variant="caption" color={colors.faint} style={{ marginTop: 4 }}>{t('order.placedOn', { date: formatDateTime(order.created_at, i18n.language) })}</T>
      </Card>

      {order.status === 'approved' && (
        <>
          <Banner tone="success" icon="checkmark-circle" text={`${t('order.approvedTitle')} ${t('order.approvedBody')}`} />
          <Button title={t('order.viewPasses')} icon="ticket" onPress={() => { router.dismissAll(); router.replace('/(tabs)/passes'); }} />
        </>
      )}
      {order.status === 'rejected' && (
        <>
          <Banner tone="danger" icon="close-circle" text={`${t('order.rejectedTitle')}${order.reject_reason ? ` — ${order.reject_reason}` : ''}`} />
          <Button title={t('order.tryAgain')} variant="secondary" onPress={() => router.replace(`/event/${order.event_id}`)} />
        </>
      )}
      {order.status === 'cancelled' && <Banner tone="neutral" icon="remove-circle" text={order.reject_reason === 'expired' ? t('order.expired') : t('common.cancelled')} />}

      {pending && !expired && order.payment && (
        <>
          {!submitted && order.expires_at && <Banner tone="warning" icon="hourglass" text={t('order.expiresIn', { time: formatCountdown(order.expires_at, now) })} />}
          <SectionTitle>{t('order.step1')}</SectionTitle>
          <Card>
            <T variant="display" color={colors.primary}>{formatINR(order.payment.amount)}</T>
            <Divider />
            <Row style={{ justifyContent: 'space-between' }}>
              <View style={{ flex: 1 }}><T variant="caption" color={colors.muted}>{t('order.upiId')}</T><T variant="heading" selectable>{order.payment.upi_id}</T></View>
              <Button title={t('common.copy')} size="sm" variant="secondary" icon="copy-outline" onPress={async () => { await Clipboard.setStringAsync(order.payment!.upi_id ?? ''); toast(t('common.copied')); }} />
            </Row>
            <T variant="caption" color={colors.muted} style={{ marginTop: space.sm }}>{t('order.payee')}: {order.payment.payee_name}</T>
            <T variant="caption" color={colors.muted}>{t('order.note')}: {order.payment.note}</T>
            <Button title={t('order.payViaUpi')} icon="phone-portrait-outline" onPress={payViaUpi} style={{ marginTop: space.md }} disabled={!order.payment.upi_uri} />
          </Card>

          <SectionTitle>{t('order.step2')}</SectionTitle>
          <Card style={{ gap: space.md }}>
            {submitted && <Banner tone="info" icon="time" text={`${t('order.inReview')} — ${t('order.waitingNote')}`} />}
            <T variant="label" color={colors.muted}>{t('order.screenshot')}</T>
            {shot ? <Image source={{ uri: shot.uri }} style={{ height: 220, borderRadius: 12, backgroundColor: colors.border }} contentFit="contain" /> : order.has_screenshot ? (
              <Row><Ionicons name="checkmark-circle" size={20} color={colors.success} /><T color={colors.success}>{t('order.screenshot')} ✓</T></Row>
            ) : null}
            <Button title={shot || order.has_screenshot ? t('order.changeScreenshot') : t('order.pickScreenshot')} icon="image-outline" variant="secondary" onPress={pickShot} />
            <Input label={t('order.utr')} value={utr} onChangeText={(v) => { setUtr(sanitizeUtr(v)); setError(null); }} keyboardType="number-pad" maxLength={14} helper={t('order.utrHelp')} placeholder="402611223344" />
            <Input label={t('order.amountPaid')} value={paid} onChangeText={(v) => setPaid(v.replace(/\D/g, ''))} keyboardType="number-pad" />
            {error ? <Banner tone="danger" text={error} /> : null}
            <Button title={submitted ? t('order.resubmit') : t('order.submitProof')} onPress={submit} loading={busy} />
          </Card>
          <Button title={t('order.cancelOrder')} variant="ghost" onPress={cancel} />
        </>
      )}
      {expired && <Banner tone="danger" text={t('order.expired')} />}
    </Screen>
  );
}
