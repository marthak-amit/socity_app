import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:share_plus/share_plus.dart';

import '../../core/api.dart';
import '../../core/colors.dart';
import '../../core/models.dart';
import '../../core/utils.dart';
import '../../l10n/strings.dart';
import '../../state/providers.dart';
import '../../ui/widgets.dart';

class ReportScreen extends ConsumerStatefulWidget {
  const ReportScreen({super.key, required this.id});
  final String id;
  @override
  ConsumerState<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends ConsumerState<ReportScreen> {
  String? _exporting;

  Future<void> _export(String sid, String format, String title) async {
    final t = ref.read(trProvider);
    setState(() => _exporting = format);
    try {
      final bytes = await ref.read(apiProvider).download('/societies/$sid/events/${widget.id}/report/export?format=$format');
      final mime = format == 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
      final name = 'report-${widget.id}.$format';
      await SharePlus.instance.share(ShareParams(files: [XFile.fromData(bytes, mimeType: mime, name: name)], fileNameOverrides: [name], title: title));
    } catch (e) {
      if (mounted) toast(context, errorText(t, e), tone: Tone.danger);
    } finally {
      if (mounted) setState(() => _exporting = null);
    }
  }

  Widget _stat(String label, String value, [Color? color]) => AppCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label, style: const TextStyle(color: AppColors.muted, fontSize: 12)),
          Text(value, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: color)),
        ]),
      );

  Widget _table(List<String> head, List<List<String>> rows) => AppCard(
        padding: const EdgeInsets.all(12),
        child: Column(children: [
          Row(children: [for (var i = 0; i < head.length; i++) Expanded(flex: i == 0 ? 2 : 1, child: Text(head[i], textAlign: i == 0 ? TextAlign.start : TextAlign.end, style: const TextStyle(color: AppColors.muted, fontSize: 12)))]),
          for (final r in rows)
            Container(
              padding: const EdgeInsets.symmetric(vertical: 6),
              decoration: const BoxDecoration(border: Border(top: BorderSide(color: AppColors.border))),
              child: Row(children: [for (var i = 0; i < r.length; i++) Expanded(flex: i == 0 ? 2 : 1, child: Text(r[i], textAlign: i == 0 ? TextAlign.start : TextAlign.end, style: const TextStyle(fontWeight: FontWeight.w600)))]),
            ),
        ]),
      );

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    final sid = ref.watch(activeSocietyProvider).societyId;
    if (sid == null) return const Scaffold(body: LoadingView());
    final q = ref.watch(reportProvider((sid: sid, id: widget.id)));
    return Scaffold(
      appBar: AppBar(title: Text(t('report.title'))),
      body: AsyncBody<Report>(
        value: q,
        onRetry: () => ref.invalidate(reportProvider((sid: sid, id: widget.id))),
        builder: (r) => RefreshScroll(onRefresh: () async => ref.read(dataVersionProvider.notifier).bump(), children: [
          Text(r.title, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
          Row(children: [
            Expanded(child: _stat(t('report.collected'), formatInr(r.total('collected_amount')), AppColors.success)),
            const SizedBox(width: 8),
            Expanded(child: _stat(t('report.pendingReview'), '${formatInr(r.total('pending_amount'))} (${r.total('pending_count')})', AppColors.warning)),
          ]),
          Row(children: [
            Expanded(child: _stat(t('report.passesSold'), '${r.total('passes_sold')}')),
            const SizedBox(width: 8),
            Expanded(child: _stat(t('report.passesScanned'), '${r.total('passes_scanned')}', AppColors.primary)),
          ]),
          if (r.total('awaiting_payment_count') > 0) Text('${r.total('awaiting_payment_count')} ${t('report.unpaidOrders')}', style: const TextStyle(color: AppColors.muted, fontSize: 12)),
          SectionTitle(t('report.byTier')),
          _table(['', t('common.sold'), '₹', t('scan.scanned')], [
            for (final x in r.byTier) ['${x['name']}\n${(x['price'] as num) > 0 ? formatInr(x['price'] as num) : t('common.free')} · ${x['capacity']}', '${x['sold']}${(x['pending'] as num) > 0 ? '+${x['pending']}' : ''}', formatInr(x['collected'] as num), '${x['scanned']}'],
          ]),
          SectionTitle(t('report.byWing')),
          _table(['', t('report.orders'), t('report.passes'), '₹'], r.byWing.isEmpty ? [['—', '0', '0', '₹0']] : [for (final x in r.byWing) ['${x['wing']}', '${x['orders']}', '${x['passes']}', formatInr(x['collected'] as num)]]),
          if (r.byDay.length > 1) ...[
            SectionTitle(t('report.byDay')),
            _table(['', t('scan.scanned'), t('scan.expected')], [for (final d in r.byDay) [formatDay(d['date'] as String), '${d['scanned']}', '${d['expected']}']]),
          ],
          kGapS,
          Row(children: [
            Expanded(child: AppButton(t('report.exportCsv'), icon: Icons.description_outlined, variant: 'secondary', loading: _exporting == 'csv', onPressed: () => _export(sid, 'csv', r.title))),
            const SizedBox(width: 8),
            Expanded(child: AppButton(t('report.exportXlsx'), icon: Icons.grid_on, loading: _exporting == 'xlsx', onPressed: () => _export(sid, 'xlsx', r.title))),
          ]),
        ]),
      ),
    );
  }
}
