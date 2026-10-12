import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/colors.dart';
import '../state/auth.dart';
import '../state/providers.dart';
import '../l10n/strings.dart';
import '../ui/widgets.dart';

class OnboardingScreen extends ConsumerWidget {
  const OnboardingScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(trProvider);
    final active = ref.watch(activeSocietyProvider);
    final user = ref.watch(authProvider.select((s) => s.user));
    final first = (user?.name ?? '').split(' ').first;
    Widget option(IconData icon, Color tint, String title, String sub, String route) => AppCard(
          onTap: () => context.push(route),
          child: Row(children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(color: tint.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(14)),
              child: Icon(icon, size: 26, color: tint),
            ),
            const SizedBox(width: 12),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
              Text(sub, style: const TextStyle(color: AppColors.muted, fontSize: 12)),
            ])),
            const Icon(Icons.chevron_right, color: AppColors.faint),
          ]),
        );

    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async => ref.read(dataVersionProvider.notifier).bump(),
          child: ListView(padding: const EdgeInsets.all(16), children: [
            const SizedBox(height: 24),
            Text(t('onboarding.title', {'name': first.isEmpty ? '' : ', $first'}), style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w800)),
            Text(t('onboarding.subtitle'), style: const TextStyle(color: AppColors.muted)),
            kGap,
            for (final m in active.pending) ...[
              AppCard(
                color: AppColors.warningSoft,
                borderColor: AppColors.warning,
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    const Icon(Icons.schedule, color: AppColors.warning),
                    const SizedBox(width: 8),
                    Text(t('onboarding.pendingTitle'), style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
                  ]),
                  const SizedBox(height: 4),
                  Text(t('onboarding.pendingBody', {'name': m.society.name})),
                  const SizedBox(height: 8),
                  AppButton(t('onboarding.checkStatus'), variant: 'secondary', small: true, expand: false, onPressed: () => ref.read(dataVersionProvider.notifier).bump()),
                ]),
              ),
              kGap,
            ],
            option(Icons.login, AppColors.primary, t('onboarding.join'), t('onboarding.joinSub'), '/join'),
            kGap,
            option(Icons.apartment, AppColors.success, t('onboarding.create'), t('onboarding.createSub'), '/create-society'),
            kGap,
            active.societyId != null
                ? AppButton(t('common.back'), variant: 'ghost', onPressed: () => context.go('/'))
                : AppButton(t('onboarding.signOut'), variant: 'ghost', onPressed: () => ref.read(authProvider.notifier).logout()),
          ]),
        ),
      ),
    );
  }
}
