import React, { useState } from 'react';
import { View } from 'react-native';
import * as Sharing from 'expo-sharing';
import { useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { downloadExport } from '@/api/client';
import { Button, Card, ErrorState, LoadingView, Row, Screen, SectionTitle, T, errorMessage, toast } from '@/components/ui';
import { useReport } from '@/hooks/queries';
import { useActiveSociety } from '@/hooks/useSociety';
import { colors, space } from '@/theme';
import { formatDay } from '@/utils/dates';
import { formatINR } from '@/utils/money';

function Stat({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <Card style={{ flex: 1, minWidth: '45%' }}>
      <T variant="caption" color={colors.muted}>{label}</T>
      <T variant="title" color={color}>{value}</T>
    </Card>
  );
}

function Table({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <Card style={{ padding: space.md }}>
      <Row>{head.map((h, i) => <T key={`${h}-${i}`} variant="caption" color={colors.muted} style={{ flex: i === 0 ? 2 : 1, textAlign: i === 0 ? 'left' : 'right' }}>{h}</T>)}</Row>
      {rows.map((row, ri) => (
        <Row key={ri} style={{ paddingVertical: 6, borderTopWidth: 1, borderTopColor: colors.border }}>
          {row.map((c, i) => <T key={i} variant="label" style={{ flex: i === 0 ? 2 : 1, textAlign: i === 0 ? 'left' : 'right' }}>{c}</T>)}
        </Row>
      ))}
    </Card>
  );
}

export default function ReportScreen() {
  const { t, i18n } = useTranslation();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { societyId } = useActiveSociety();
  const q = useReport(societyId, id);
  const [exporting, setExporting] = useState<string | null>(null);
  if (q.isLoading) return <LoadingView />;
  if (q.isError || !q.data) return <ErrorState error={q.error} onRetry={q.refetch} />;
  const r = q.data;

  const exportFile = async (format: 'csv' | 'xlsx') => {
    setExporting(format);
    try {
      const uri = await downloadExport(`/societies/${societyId}/events/${id}/report/export?format=${format}`, `report-${id}.${format}`);
      if (await Sharing.isAvailableAsync()) await Sharing.shareAsync(uri, { dialogTitle: r.title });
    } catch (e) {
      toast(errorMessage(e, t), 'danger');
    } finally {
      setExporting(null);
    }
  };

  return (
    <Screen refreshing={q.isRefetching} onRefresh={() => q.refetch()}>
      <T variant="title">{r.title}</T>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.sm }}>
        <Stat label={t('report.collected')} value={formatINR(r.totals.collected_amount)} color={colors.success} />
        <Stat label={t('report.pendingReview')} value={`${formatINR(r.totals.pending_amount)} (${r.totals.pending_count})`} color={colors.warning} />
        <Stat label={t('report.passesSold')} value={r.totals.passes_sold} />
        <Stat label={t('report.passesScanned')} value={r.totals.passes_scanned} color={colors.primary} />
      </View>
      {r.totals.awaiting_payment_count > 0 && <T variant="caption" color={colors.muted}>{r.totals.awaiting_payment_count} {t('report.unpaidOrders')}</T>}

      <SectionTitle>{t('report.byTier')}</SectionTitle>
      <Table head={['', t('common.sold'), '₹', t('scan.scanned')]} rows={r.by_tier.map((x) => [`${x.name}\n${x.price ? formatINR(x.price) : t('common.free')} · ${x.capacity}`, `${x.sold}${x.pending ? `+${x.pending}` : ''}`, formatINR(x.collected), x.scanned])} />
      <SectionTitle>{t('report.byWing')}</SectionTitle>
      <Table head={['', t('report.orders'), t('report.passes'), '₹']} rows={r.by_wing.length ? r.by_wing.map((x) => [x.wing, x.orders, x.passes, formatINR(x.collected)]) : [['—', 0, 0, '₹0']]} />
      {r.by_day.length > 1 && (
        <>
          <SectionTitle>{t('report.byDay')}</SectionTitle>
          <Table head={['', t('scan.scanned'), t('scan.expected')]} rows={r.by_day.map((d) => [formatDay(d.date, i18n.language), d.scanned, d.expected])} />
        </>
      )}

      <Row style={{ marginTop: space.md }}>
        <Button title={t('report.exportCsv')} icon="document-text-outline" variant="secondary" style={{ flex: 1 }} onPress={() => exportFile('csv')} loading={exporting === 'csv'} />
        <Button title={t('report.exportXlsx')} icon="grid-outline" style={{ flex: 1 }} onPress={() => exportFile('xlsx')} loading={exporting === 'xlsx'} />
      </Row>
    </Screen>
  );
}
