import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/api.dart';
import '../core/colors.dart';
import '../core/config.dart';
import '../core/models.dart';
import '../l10n/strings.dart';
import '../state/auth.dart';
import '../state/providers.dart';
import '../ui/widgets.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});
  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  late final _name = TextEditingController(text: ref.read(authProvider).user?.name ?? '');

  Future<void> _saveName() async {
    final t = ref.read(trProvider);
    final user = ref.read(authProvider).user;
    if (_name.text.trim().length < 2 || _name.text.trim() == user?.name) return;
    try {
      final me = Me.fromJson(await ref.read(apiProvider).patch('/me', {'name': _name.text.trim()}));
      await ref.read(authProvider.notifier).setUser(me.user);
      ref.read(dataVersionProvider.notifier).bump();
      if (mounted) toast(context, t('settings.saved'), tone: Tone.success);
    } catch (e) {
      if (mounted) toast(context, errorText(t, e), tone: Tone.danger);
    }
  }

  Future<void> _lang(String code) async {
    await ref.read(authProvider.notifier).setLocale(code);
    try {
      await ref.read(apiProvider).patch('/me', {'locale': code});
    } catch (_) {/* offline: the local choice still applies */}
  }

  Future<void> _leave() async {
    final t = ref.read(trProvider);
    final sid = ref.read(activeSocietyProvider).societyId;
    if (sid == null || !await confirmDialog(context, t, t('manage.leave'), message: t('manage.leaveConfirm'), confirmText: t('manage.leave'), destructive: true)) return;
    try {
      await ref.read(apiProvider).post('/societies/$sid/leave');
      await ref.read(authProvider.notifier).setActiveSociety(null);
      ref.read(dataVersionProvider.notifier).bump();
      if (mounted) context.go('/');
    } catch (e) {
      if (mounted) toast(context, errorText(t, e), tone: Tone.danger);
    }
  }

  Future<void> _signOut() async {
    final t = ref.read(trProvider);
    if (!await confirmDialog(context, t, t('settings.signOut'), message: t('settings.signOutConfirm'), confirmText: t('settings.signOut'), destructive: true)) return;
    await ref.read(authProvider.notifier).logout();
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    final lang = ref.watch(langProvider);
    final user = ref.watch(authProvider.select((s) => s.user));
    final active = ref.watch(activeSocietyProvider);
    return AppScaffold(
      title: t('settings.title'),
      body: ListView(padding: kPad, children: [
        AppCard(
          child: Row(children: [
            Avatar(user?.name, size: 52),
            const SizedBox(width: 12),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(user?.name ?? '', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
              Text('${t('settings.phone')}: ${user?.phone ?? ''}', style: const TextStyle(color: AppColors.muted, fontSize: 12)),
            ])),
          ]),
        ),
        kGap,
        AppField(controller: _name, label: t('settings.name'), textCapitalization: TextCapitalization.words, onSubmitted: (_) => _saveName(), suffix: IconButton(icon: const Icon(Icons.check), onPressed: _saveName)),
        SectionTitle(t('settings.language')),
        kGapS,
        Wrap(spacing: 8, children: [for (final l in supportedLanguages) TagChip(l.$2, selected: lang == l.$1, onTap: () => _lang(l.$1))]),
        kGap,
        if (active.societyId != null && active.role != null && active.role!.name != 'owner') AppButton(t('manage.leave'), variant: 'ghost', onPressed: _leave),
        AppButton(t('settings.signOut'), variant: 'danger', icon: Icons.logout, onPressed: _signOut),
        kGap,
        Center(child: Text(t('settings.version', {'v': appVersion}), style: const TextStyle(color: AppColors.faint, fontSize: 12))),
      ]),
    );
  }
}
