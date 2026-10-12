import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'dart:convert';

import '../../core/api.dart';
import '../../core/colors.dart';
import '../../core/models.dart';
import '../../core/utils.dart';
import '../../l10n/strings.dart';
import '../../state/providers.dart';
import '../../ui/paged.dart';
import '../../ui/widgets.dart';

class MembersScreen extends ConsumerStatefulWidget {
  const MembersScreen({super.key});
  @override
  ConsumerState<MembersScreen> createState() => _MembersScreenState();
}

class _MembersScreenState extends ConsumerState<MembersScreen> {
  String _tab = 'pending';
  String _q = '';
  bool _minTwoAdminsWarn = false;

  Future<void> _act(Future<Json> Function() fn, {String? ok}) async {
    final t = ref.read(trProvider);
    try {
      final r = await fn();
      ref.read(dataVersionProvider.notifier).bump();
      final w = (r['warnings'] as List?)?.cast<String>() ?? const [];
      if (mounted) setState(() => _minTwoAdminsWarn = w.contains('min_two_admins'));
      if (ok != null && mounted) toast(context, ok, tone: Tone.success);
    } catch (e) {
      if (mounted) toast(context, errorText(t, e), tone: Tone.danger);
    }
  }

  Future<void> _importCsv(String sid) async {
    final t = ref.read(trProvider);
    final file = await FilePicker.pickFile(type: FileType.custom, allowedExtensions: ['csv', 'txt']);
    if (file == null) return;
    try {
      final bytes = await file.readAsBytes();
      final r = await ref.read(apiProvider).post('/societies/$sid/members/import', {'csv_text': utf8.decode(bytes, allowMalformed: true)});
      ref.read(dataVersionProvider.notifier).bump();
      final errs = (r['errors'] as List).length;
      if (mounted) toast(context, '${t('members.importResult', {'created': r['created'], 'updated': r['updated'], 'activated': r['activated']})}${errs > 0 ? ' · ${t('members.importErrors', {'n': errs})}' : ''}', tone: errs > 0 ? Tone.neutral : Tone.success);
    } catch (e) {
      if (mounted) toast(context, errorText(t, e), tone: Tone.danger);
    }
  }

  void _sheet(Member m, String sid, Role? actor) {
    final t = ref.read(trProvider);
    String label(Role r) => switch (r) { Role.admin => t('members.makeAdmin'), Role.volunteer => t('members.makeVolunteer'), _ => t('members.makeMember') };
    showModalBottomSheet(
      context: context,
      backgroundColor: AppColors.bg,
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Text(m.display, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
            Text(t('members.changeRole'), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
            kGapS,
            for (final r in assignableRoles(actor, m.role)) ...[
              AppButton(label(r), variant: 'secondary', onPressed: () {
                Navigator.pop(ctx);
                _act(() => ref.read(apiProvider).patch('/societies/$sid/members/${m.id}', {'role': r.name}));
              }),
              kGapS,
            ],
            AppButton(t('members.removeMember'), variant: 'danger', onPressed: () async {
              Navigator.pop(ctx);
              if (await confirmDialog(context, t, t('members.removeMember'), message: t('members.removeConfirm', {'name': m.display}), confirmText: t('common.remove'), destructive: true)) {
                _act(() => ref.read(apiProvider).delete('/societies/$sid/members/${m.id}'));
              }
            }),
          ]),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    final active = ref.watch(activeSocietyProvider);
    final sid = active.societyId;
    if (sid == null) return const Scaffold(body: LoadingView());
    final pendingCount = ref.watch(countProvider((path: '/societies/$sid/members', query: {'status': 'pending'}))).value;
    return Scaffold(
      appBar: AppBar(title: Text(t('members.title'))),
      body: PagedListView<Member>(
        key: ValueKey('members-$_tab-$_q'),
        path: '/societies/$sid/members',
        query: {'status': _tab, if (_q.isNotEmpty && _tab == 'active') 'q': _q},
        parse: Member.fromJson,
        pageSize: 30,
        gap: 8,
        empty: EmptyState(icon: Icons.people_outline, title: _tab == 'pending' ? t('members.noRequests') : t('members.empty')),
        header: Column(children: [
          SegmentedTabs<String>(value: _tab, onChanged: (v) => setState(() => _tab = v), options: [('pending', t('members.requests'), pendingCount), ('active', t('members.active'), null)]),
          if (_tab == 'active') ...[kGapS, AppField(hint: t('members.searchPlaceholder'), onSubmitted: (v) => setState(() => _q = v.trim()), onChanged: (v) { if (v.isEmpty && _q.isNotEmpty) setState(() => _q = ''); })],
          if (_minTwoAdminsWarn) ...[kGapS, InfoBanner(t('members.minTwoAdmins'))],
        ]),
        footer: _tab == 'active'
            ? Padding(
                padding: const EdgeInsets.only(top: 16, bottom: 40),
                child: Column(children: [
                  AppButton(t('members.importCsv'), icon: Icons.description_outlined, variant: 'secondary', onPressed: () => _importCsv(sid)),
                  const SizedBox(height: 6),
                  Text(t('members.importHelp'), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                ]),
              )
            : null,
        itemBuilder: (_, m, _) {
          final canManage = assignableRoles(active.role, m.role).isNotEmpty || (active.role == Role.owner && m.role != Role.owner);
          return AppCard(
            onTap: _tab == 'active' && canManage ? () => _sheet(m, sid, active.role) : null,
            child: Column(children: [
              Row(children: [
                Avatar(m.display),
                const SizedBox(width: 12),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(m.display, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                  Text('${m.phone}${m.flatNo != null || m.wing != null ? ' · ${[m.wing, m.flatNo].whereType<String>().join('-')}' : ''}', style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                ])),
                if (_tab == 'active' && m.role != Role.member) AppBadge(t('roles.${m.role.name}'), tone: m.role == Role.volunteer ? Tone.info : Tone.primary),
              ]),
              if (_tab == 'pending') ...[
                kGap,
                Row(children: [
                  Expanded(child: AppButton(t('common.reject'), variant: 'secondary', small: true, onPressed: () => _act(() => ref.read(apiProvider).post('/societies/$sid/members/${m.id}/reject'), ok: t('common.rejected')))),
                  const SizedBox(width: 8),
                  Expanded(child: AppButton(t('common.approve'), variant: 'success', small: true, onPressed: () => _act(() => ref.read(apiProvider).post('/societies/$sid/members/${m.id}/approve'), ok: t('common.approved')))),
                ]),
              ],
            ]),
          );
        },
      ),
    );
  }
}
