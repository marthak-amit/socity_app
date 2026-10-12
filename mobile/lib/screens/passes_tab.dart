import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/colors.dart';
import '../core/models.dart';
import '../core/utils.dart';
import '../l10n/strings.dart';
import '../state/providers.dart';
import '../ui/widgets.dart';

class PassesTab extends ConsumerWidget {
  const PassesTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(trProvider);
    final q = ref.watch(myPassesProvider);
    return q.when(
      loading: () => const LoadingView(),
      error: (e, _) => ErrorView(e, onRetry: () => ref.invalidate(myPassesProvider)),
      data: (res) {
        final now = DateTime.now();
        final byEvent = <String, List<PassT>>{};
        for (final p in res.passes) {
          byEvent.putIfAbsent(p.event.id, () => []).add(p);
        }
        final groups = byEvent.values.toList();
        final upcoming = groups.where((g) => !g.first.event.endsAt.isBefore(now)).toList()..sort((a, b) => a.first.event.startsAt.compareTo(b.first.event.startsAt));
        final past = groups.where((g) => g.first.event.endsAt.isBefore(now)).toList()..sort((a, b) => b.first.event.startsAt.compareTo(a.first.event.startsAt));
        final children = <Widget>[
          if (res.offline) InfoBanner(t('passes.offlineBanner'), icon: Icons.cloud_off),
          for (final (label, list) in [(t('passes.upcoming'), upcoming), (t('passes.past'), past)])
            for (final g in list) ...[
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(label.toUpperCase(), style: const TextStyle(fontSize: 12, color: AppColors.muted)),
                  Text(g.first.event.title, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
                  Text('${g.first.event.societyName} · ${formatDateRange(g.first.event.startsAt, g.first.event.endsAt)}', style: const TextStyle(fontSize: 12, color: AppColors.muted)),
                ]),
              ),
              for (var i = 0; i < g.length; i++) _PassCard(pass: g[i], index: i, total: g.length),
            ],
        ];
        if (res.passes.isEmpty) {
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(myPassesProvider),
            child: ListView(children: [SizedBox(height: 420, child: EmptyState(icon: Icons.confirmation_number_outlined, title: t('passes.empty'), subtitle: t('passes.emptySub')))]),
          );
        }
        return RefreshScroll(gap: 8, onRefresh: () async => ref.read(dataVersionProvider.notifier).bump(), children: children);
      },
    );
  }
}

class _PassCard extends ConsumerWidget {
  const _PassCard({required this.pass, required this.index, required this.total});
  final PassT pass;
  final int index, total;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(trProvider);
    return Opacity(
      opacity: pass.revoked ? 0.55 : 1,
      child: AppCard(
        onTap: () => context.push('/pass/${pass.id}'),
        child: Row(children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(color: AppColors.primarySoft, borderRadius: BorderRadius.circular(12)),
            child: const Icon(Icons.qr_code_2, size: 26, color: AppColors.primary),
          ),
          const SizedBox(width: 12),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(pass.holderName, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
            Text('${pass.tierName}${pass.holderType == 'guest' ? ' · ${t('passes.guest')}' : ''} · ${t('passes.ticketOf', {'i': index + 1, 'n': total})}', style: const TextStyle(color: AppColors.muted, fontSize: 12)),
            if (pass.scannedDates.isNotEmpty) Text(t('passes.scannedOn', {'date': pass.scannedDates.map(formatDay).join(', ')}), style: const TextStyle(color: AppColors.success, fontSize: 12)),
          ])),
          if (pass.revoked) AppBadge(t('passes.revoked'), tone: Tone.danger) else if (pass.scannedDates.isNotEmpty) AppBadge(t('passes.used'), tone: Tone.success) else const Icon(Icons.chevron_right, color: AppColors.faint),
        ]),
      ),
    );
  }
}
