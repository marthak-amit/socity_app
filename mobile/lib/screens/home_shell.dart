import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/colors.dart';
import '../core/utils.dart';
import '../l10n/strings.dart';
import '../state/auth.dart';
import '../state/providers.dart';
import '../ui/widgets.dart';
import 'events_tab.dart';
import 'gallery_tab.dart';
import 'manage_tab.dart';
import 'passes_tab.dart';
import 'scan_tab.dart';

/// Role-aware bottom navigation: Events · My Passes · Gallery · Scan (volunteer/admin) · Manage (admin/owner).
class HomeShell extends ConsumerStatefulWidget {
  const HomeShell({super.key, this.initialTab});
  final String? initialTab;
  @override
  ConsumerState<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends ConsumerState<HomeShell> {
  TabKey _tab = TabKey.events;

  @override
  void initState() {
    super.initState();
    final i = TabKey.values.where((k) => k.name == widget.initialTab);
    if (i.isNotEmpty) _tab = i.first;
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    final active = ref.watch(activeSocietyProvider);
    final tabs = tabsForRole(active.role);
    final current = tabs.contains(_tab) ? _tab : TabKey.events;
    final labels = {
      TabKey.events: (Icons.calendar_today_outlined, Icons.calendar_today, t('tabs.home')),
      TabKey.passes: (Icons.confirmation_number_outlined, Icons.confirmation_number, t('tabs.passes')),
      TabKey.gallery: (Icons.photo_library_outlined, Icons.photo_library, t('tabs.gallery')),
      TabKey.scan: (Icons.qr_code_scanner_outlined, Icons.qr_code_scanner, t('tabs.scan')),
      TabKey.manage: (Icons.business_center_outlined, Icons.business_center, t('tabs.manage')),
    };

    return Scaffold(
      appBar: AppBar(
        titleSpacing: 16,
        title: const SocietySwitcher(),
        actions: [
          IconButton(tooltip: 'Orders', icon: const Icon(Icons.receipt_long_outlined), onPressed: () => context.push('/orders')),
          IconButton(tooltip: 'Settings', icon: const Icon(Icons.settings_outlined), onPressed: () => context.push('/settings')),
        ],
      ),
      body: active.loading && active.me == null
          ? const LoadingView()
          : active.error != null && active.me == null
              ? ErrorView(active.error!, onRetry: () => ref.read(dataVersionProvider.notifier).bump())
              : switch (current) {
                  TabKey.events => const EventsTab(),
                  TabKey.passes => const PassesTab(),
                  TabKey.gallery => const GalleryTab(),
                  TabKey.scan => const ScanTab(),
                  TabKey.manage => const ManageTab(),
                },
      bottomNavigationBar: NavigationBar(
        selectedIndex: tabs.indexOf(current),
        onDestinationSelected: (i) => setState(() => _tab = tabs[i]),
        destinations: [
          for (final k in tabs) NavigationDestination(icon: Icon(labels[k]!.$1), selectedIcon: Icon(labels[k]!.$2, color: AppColors.primary), label: labels[k]!.$3),
        ],
      ),
    );
  }
}

/// Header control: the active society + role, with a bottom sheet to switch (roles differ per society).
class SocietySwitcher extends ConsumerWidget {
  const SocietySwitcher({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(trProvider);
    final active = ref.watch(activeSocietyProvider);
    final s = active.society;
    return InkWell(
      onTap: () => showModalBottomSheet(
        context: context,
        isScrollControlled: true,
        backgroundColor: AppColors.bg,
        builder: (_) => const _SwitcherSheet(),
      ),
      borderRadius: BorderRadius.circular(8),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Flexible(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
            Text(s?.name ?? t('common.appName'), overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
            if (active.role != null)
              Text('${t('roles.${active.role!.name}')}${s != null ? ' · ${s.city}' : ''}', overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, color: AppColors.muted, fontWeight: FontWeight.w400)),
          ]),
        ),
        const Icon(Icons.keyboard_arrow_down, color: AppColors.muted),
      ]),
    );
  }
}

class _SwitcherSheet extends ConsumerWidget {
  const _SwitcherSheet();
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(trProvider);
    final active = ref.watch(activeSocietyProvider);
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(t('switcher.title'), style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
          kGap,
          for (final m in active.memberships) ...[
            AppCard(
              selected: m.society.id == active.societyId,
              onTap: m.active
                  ? () {
                      ref.read(authProvider.notifier).setActiveSociety(m.society.id);
                      Navigator.pop(context);
                    }
                  : null,
              child: Row(children: [
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(m.society.name, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                  Text('${m.society.city} · ${t('roles.${m.role.name}')}', style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                ])),
                if (!m.active)
                  AppBadge(t('switcher.pending'), tone: Tone.warning)
                else if (m.society.suspended)
                  AppBadge(t('switcher.suspended'), tone: Tone.danger)
                else if (m.society.id == active.societyId)
                  const Icon(Icons.check_circle, color: AppColors.primary),
              ]),
            ),
            kGapS,
          ],
          AppButton(t('switcher.addAnother'), variant: 'secondary', icon: Icons.add, onPressed: () {
            Navigator.pop(context);
            context.push('/onboarding?add=1');
          }),
        ]),
      ),
    );
  }
}
