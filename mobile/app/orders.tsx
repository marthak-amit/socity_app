import React from 'react';
import { FlatList, RefreshControl, View } from 'react-native';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { Badge, Card, EmptyState, ErrorState, LoadingView, Row, T } from '@/components/ui';
import { flat, useMyOrders } from '@/hooks/queries';
import { useActiveSociety } from '@/hooks/useSociety';
import { colors, space } from '@/theme';
import { formatDateTime } from '@/utils/dates';
import { formatINR } from '@/utils/money';

export default function Orders() {
  const { t, i18n } = useTranslation();
  const { societyId } = useActiveSociety();
  const q = useMyOrders(societyId);
  const orders = flat(q.data);
  if (q.isLoading) return <LoadingView />;
  if (q.isError && !orders.length) return <ErrorState error={q.error} onRetry={q.refetch} />;
  return (
    <FlatList
      data={orders} keyExtractor={(o) => o.id} contentContainerStyle={{ padding: space.lg, gap: space.md, flexGrow: 1 }}
      refreshControl={<RefreshControl refreshing={q.isRefetching} onRefresh={() => q.refetch()} tintColor={colors.primary} />}
      onEndReached={() => q.hasNextPage && q.fetchNextPage()}
      ListEmptyComponent={<EmptyState icon="receipt-outline" title={t('order.noOrders')} />}
      renderItem={({ item: o }) => (
        <Card onPress={() => router.push(`/order/${o.id}`)}>
          <Row style={{ justifyContent: 'space-between' }}>
            <View style={{ flex: 1 }}>
              <T variant="heading" numberOfLines={1}>{o.event_title}</T>
              <T variant="caption" color={colors.muted}>{o.ref_code} · {formatDateTime(o.created_at, i18n.language)}</T>
              <T variant="caption" color={colors.muted}>{o.items.map((i) => `${i.qty}× ${i.tier_name}`).join(', ')}</T>
            </View>
            <View style={{ alignItems: 'flex-end', gap: 4 }}>
              <T variant="heading">{formatINR(o.total_amount)}</T>
              <Badge tone={o.status === 'approved' ? 'success' : o.status === 'pending' ? 'warning' : 'danger'}
                text={o.status === 'pending' ? (o.payment_submitted_at ? t('order.inReview') : t('order.awaitingPayment')) : t(`common.${o.status}`)} />
            </View>
          </Row>
        </Card>
      )}
    />
  );
}
