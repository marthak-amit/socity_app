import React, { useMemo, useState } from 'react';
import { Pressable, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { post } from '@/api/client';
import type { Holder, Order } from '@/api/types';
import { Banner, Button, Card, Chip, ErrorState, Input, Ionicons, LoadingView, Row, Screen, T, errorMessage, toast } from '@/components/ui';
import { useEvent } from '@/hooks/queries';
import { useActiveSociety } from '@/hooks/useSociety';
import { colors, space } from '@/theme';
import { formatINR, priceLabel } from '@/utils/money';

type Sel = Record<string, Holder[]>; // tier id → one holder per pass

export default function Buy() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { societyId, user } = useActiveSociety();
  const q = useEvent(societyId, id);
  const [sel, setSel] = useState<Sel>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const ev = q.data;
  const total = useMemo(() => (ev ? ev.tiers.reduce((sum, tier) => sum + tier.price * (sel[tier.id]?.length ?? 0), 0) : 0), [ev, sel]);
  const count = Object.values(sel).reduce((n, h) => n + h.length, 0);

  if (q.isLoading) return <LoadingView />;
  if (q.isError || !ev) return <ErrorState error={q.error} onRetry={q.refetch} />;

  const setQty = (tierId: string, delta: number, max: number, allowGuests: boolean) => {
    setError(null);
    setSel((prev) => {
      const cur = prev[tierId] ?? [];
      const n = Math.max(0, Math.min(max, cur.length + delta));
      if (n === cur.length) return prev;
      const next = cur.slice(0, n);
      while (next.length < n) {
        const first = count === 0 && next.length === 0 && !Object.values(prev).some((h) => h.length);
        next.push({ name: first ? user?.name ?? '' : '', type: first || !allowGuests ? 'member' : 'guest' });
      }
      const out = { ...prev, [tierId]: next };
      if (!n) delete out[tierId];
      return out;
    });
  };
  const setHolder = (tierId: string, i: number, patch: Partial<Holder>) =>
    setSel((prev) => ({ ...prev, [tierId]: prev[tierId].map((h, idx) => (idx === i ? { ...h, ...patch } : h)) }));

  const submit = async () => {
    if (!count) return setError(t('buy.pickAtLeastOne'));
    if (Object.values(sel).some((hs) => hs.some((h) => !h.name.trim()))) return setError(t('buy.nameRequired'));
    setLoading(true);
    setError(null);
    try {
      const order = await post<Order>(`/societies/${societyId}/events/${ev.id}/orders`, {
        items: Object.entries(sel).map(([tier_id, holders]) => ({ tier_id, qty: holders.length, holders: holders.map((h) => ({ name: h.name.trim(), type: h.type })) })),
      });
      await Promise.all([qc.invalidateQueries({ queryKey: ['event'] }), qc.invalidateQueries({ queryKey: ['events'] }), qc.invalidateQueries({ queryKey: ['passes'] })]);
      if (order.status === 'approved') {
        toast(t('buy.freeDone'), 'success');
        router.dismissAll();
        router.replace('/(tabs)/passes');
      } else {
        router.replace(`/order/${order.id}`);
      }
    } catch (e) {
      setError(errorMessage(e, t));
      void q.refetch();
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={{ flex: 1 }}>
      <Screen style={{ paddingBottom: 140 }}>
        <T variant="title">{ev.title}</T>
        {ev.tiers.map((tier) => {
          const held = sel[tier.id] ?? [];
          const max = Math.min(tier.per_user_limit, tier.remaining);
          return (
            <Card key={tier.id} style={tier.remaining === 0 ? { opacity: 0.55 } : undefined}>
              <Row style={{ justifyContent: 'space-between' }}>
                <View style={{ flex: 1 }}>
                  <T variant="heading">{tier.name}</T>
                  <T variant="caption" color={colors.muted}>{priceLabel(tier.price)} · {tier.remaining === 0 ? t('event.soldOut') : t('event.left', { n: tier.remaining })}</T>
                </View>
                <Row gap={4}>
                  <Pressable onPress={() => setQty(tier.id, -1, max, tier.allow_guests)} disabled={!held.length} style={[stepper, !held.length && { opacity: 0.35 }]} accessibilityLabel="Decrease"><Ionicons name="remove" size={20} color={colors.primary} /></Pressable>
                  <T variant="heading" style={{ minWidth: 28, textAlign: 'center' }}>{held.length}</T>
                  <Pressable onPress={() => setQty(tier.id, 1, max, tier.allow_guests)} disabled={held.length >= max} style={[stepper, held.length >= max && { opacity: 0.35 }]} accessibilityLabel="Increase"><Ionicons name="add" size={20} color={colors.primary} /></Pressable>
                </Row>
              </Row>
              {held.length >= max && max > 0 && <T variant="caption" color={colors.warning}>{t('buy.maxReached')} ({max})</T>}
              {held.length > 0 && (
                <View style={{ marginTop: space.md, gap: space.sm }}>
                  <T variant="label" color={colors.muted}>{t('buy.holders')}</T>
                  {held.map((h, i) => (
                    <View key={i} style={{ gap: 6 }}>
                      <Input value={h.name} onChangeText={(v) => setHolder(tier.id, i, { name: v })} placeholder={`${t('buy.holderName')} #${i + 1}`} autoCapitalize="words" maxLength={120} />
                      {tier.allow_guests && (
                        <Row>
                          <Chip label={t('buy.member')} icon="home-outline" selected={h.type === 'member'} onPress={() => setHolder(tier.id, i, { type: 'member' })} />
                          <Chip label={t('buy.guest')} icon="person-add-outline" selected={h.type === 'guest'} onPress={() => setHolder(tier.id, i, { type: 'guest' })} />
                        </Row>
                      )}
                    </View>
                  ))}
                </View>
              )}
            </Card>
          );
        })}
        {error ? <Banner tone="danger" text={error} /> : null}
      </Screen>
      <View style={{ position: 'absolute', bottom: 0, left: 0, right: 0, padding: space.lg, backgroundColor: colors.card, borderTopWidth: 1, borderTopColor: colors.border, gap: space.sm }}>
        <Row style={{ justifyContent: 'space-between' }}>
          <T color={colors.muted}>{t('buy.total')}</T>
          <T variant="title">{formatINR(total)}</T>
        </Row>
        <Button title={total === 0 && count > 0 ? t('buy.freeConfirm') : t('buy.continueToPay')} onPress={submit} loading={loading} disabled={!count} />
      </View>
    </View>
  );
}

const stepper = { width: 36, height: 36, borderRadius: 18, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' } as const;
