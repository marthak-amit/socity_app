import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../core/colors.dart';
import '../core/models.dart';
import '../core/utils.dart';
import '../l10n/strings.dart';
import '../state/providers.dart';
import '../ui/widgets.dart';

class PassCardView extends ConsumerWidget {
  const PassCardView({super.key, required this.pass, required this.index, required this.total});
  final PassT pass;
  final int index, total;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(trProvider);
    final qrSize = (MediaQuery.of(context).size.width - 140).clamp(160.0, 260.0);
    return Padding(
      padding: const EdgeInsets.all(16),
      child: SingleChildScrollView(
        child: Card(
          clipBehavior: Clip.antiAlias,
          elevation: 3,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Container(
              color: AppColors.primary,
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(pass.event.societyName, style: const TextStyle(color: Color(0xFFC7D2FE), fontSize: 12)),
                Text(pass.event.title, style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w800)),
                Text('${formatDateTime(pass.event.startsAt)}${pass.event.venue != null ? ' · ${pass.event.venue}' : ''}', style: const TextStyle(color: Color(0xFFE0E7FF), fontSize: 12)),
              ]),
            ),
            Padding(
              padding: const EdgeInsets.all(24),
              child: Opacity(
                opacity: pass.revoked ? 0.25 : 1,
                child: Column(children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.border)),
                    child: QrImageView(key: ValueKey('qr-${pass.qrToken}'), semanticsLabel: 'Pass QR code', data: pass.qrToken, size: qrSize, errorCorrectionLevel: QrErrorCorrectLevel.M, backgroundColor: Colors.white),
                  ),
                  const SizedBox(height: 12),
                  Text(t('passes.showQr'), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                ]),
              ),
            ),
            if (pass.revoked) Center(child: AppBadge(t('passes.revoked'), tone: Tone.danger)),
            Container(
              decoration: const BoxDecoration(border: Border(top: BorderSide(color: AppColors.border))),
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(t('passes.holder'), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                    Text(pass.holderName, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
                  ])),
                  AppBadge(pass.holderType == 'guest' ? t('passes.guest') : pass.tierName, tone: pass.holderType == 'guest' ? Tone.info : Tone.primary),
                ]),
                const SizedBox(height: 8),
                Row(children: [
                  Expanded(child: Text('${t('passes.tier')}: ${pass.tierName}')),
                  if (total > 1) Text(t('passes.ticketOf', {'i': index + 1, 'n': total}), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                ]),
                const SizedBox(height: 4),
                Text(
                  pass.validDays == 'all' || pass.validDates.isEmpty ? t('passes.validAllDays') : t('passes.validOnDays', {'days': pass.validDates.map(formatDay).join(', ')}),
                  style: const TextStyle(color: AppColors.muted, fontSize: 12),
                ),
                if (pass.scannedDates.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Row(children: [
                      const Icon(Icons.check_circle, size: 16, color: AppColors.success),
                      const SizedBox(width: 6),
                      Expanded(child: Text(t('passes.scannedOn', {'date': pass.scannedDates.map(formatDay).join(', ')}), style: const TextStyle(color: AppColors.success, fontSize: 12))),
                    ]),
                  ),
              ]),
            ),
          ]),
        ),
      ),
    );
  }
}

/// Full-screen QR; swipe between the passes of the same order. Reads the (offline-capable) pass list.
class PassScreen extends ConsumerWidget {
  const PassScreen({super.key, required this.id});
  final String id;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(trProvider);
    final q = ref.watch(myPassesProvider);
    return Scaffold(
      appBar: AppBar(title: Text(t('passes.title'))),
      body: AsyncBody<PassesResult>(
        value: q,
        onRetry: () => ref.invalidate(myPassesProvider),
        builder: (res) {
          final me = res.passes.where((p) => p.id == id).firstOrNull;
          if (me == null) return ErrorView(Exception('not found'), onRetry: () => ref.invalidate(myPassesProvider));
          final sib = res.passes.where((p) => p.orderId == me.orderId).toList();
          return Column(children: [
            if (res.offline) Padding(padding: const EdgeInsets.all(16), child: InfoBanner(t('passes.offlineBanner'), icon: Icons.cloud_off)),
            Expanded(
              child: PageView.builder(
                controller: PageController(initialPage: sib.indexWhere((p) => p.id == id).clamp(0, sib.length)),
                itemCount: sib.length,
                itemBuilder: (_, i) => PassCardView(pass: sib[i], index: i, total: sib.length),
              ),
            ),
            Padding(padding: const EdgeInsets.all(16), child: Text(t('passes.brightness'), textAlign: TextAlign.center, style: const TextStyle(color: AppColors.faint, fontSize: 12))),
          ]);
        },
      ),
    );
  }
}
