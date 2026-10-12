import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/colors.dart';
import '../l10n/strings.dart';
import '../state/providers.dart';
import '../ui/widgets.dart';

class ManageTab extends ConsumerWidget {
  const ManageTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(trProvider);
    final active = ref.watch(activeSocietyProvider);
    final sid = active.societyId;
    if (sid == null) return const LoadingView();
    final society = ref.watch(societyDetailProvider(sid));
    final summary = ref.watch(orderSummaryProvider(sid)).value;
    final joinReqs = ref.watch(countProvider((path: '/societies/$sid/members', query: {'status': 'pending'}))).value ?? 0;
    final photos = ref.watch(countProvider((path: '/societies/$sid/gallery', query: {'status': 'pending'}))).value ?? 0;
    final pend = summary?.pending ?? 0;

    Widget item(IconData icon, Color tint, String title, String route, {Widget? badge}) => Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: AppCard(
            onTap: () => context.push(route),
            child: Row(children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(color: tint.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(12)),
                child: Icon(icon, size: 24, color: tint),
              ),
              const SizedBox(width: 12),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(title, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
                if (badge != null) Padding(padding: const EdgeInsets.only(top: 2), child: badge),
              ])),
              const Icon(Icons.chevron_right, color: AppColors.faint),
            ]),
          ),
        );

    return RefreshIndicator(
      onRefresh: () async => ref.read(dataVersionProvider.notifier).bump(),
      child: ListView(physics: const AlwaysScrollableScrollPhysics(), padding: kPad, children: [
        for (final w in society.value?.warnings ?? const <String>[]) ...[InfoBanner(t('manage.warnings.$w')), kGapS],
        Text(t('common.youAre', {'role': t('roles.${active.role?.name ?? 'member'}')}), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
        kGapS,
        item(Icons.done_all, AppColors.success, t('manage.approvals'), '/manage/approvals',
            badge: pend > 0
                ? Wrap(spacing: 4, children: [
                    AppBadge(t('manage.pendingCount', {'n': pend}), tone: Tone.danger),
                    if ((summary?.pendingFlagged ?? 0) > 0) AppBadge('${summary!.pendingFlagged}', tone: Tone.warning, icon: Icons.flag),
                  ])
                : null),
        item(Icons.calendar_month, AppColors.primary, t('manage.events'), '/manage/events'),
        item(Icons.people, AppColors.info, t('manage.members'), '/manage/members', badge: joinReqs > 0 ? AppBadge(t('manage.pendingCount', {'n': joinReqs}), tone: Tone.danger) : null),
        item(Icons.photo_library, const Color(0xFFDB2777), t('manage.galleryMod'), '/manage/moderation', badge: photos > 0 ? AppBadge(t('manage.pendingCount', {'n': photos}), tone: Tone.danger) : null),
        item(Icons.qr_code_2, AppColors.warning, t('manage.invite'), '/manage/invite'),
        item(Icons.settings, AppColors.muted, t('manage.settings'), '/manage/society'),
      ]),
    );
  }
}
