import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api.dart';
import '../../core/colors.dart';
import '../../core/models.dart';
import '../../core/utils.dart';
import '../../l10n/strings.dart';
import '../../state/providers.dart';
import '../../ui/widgets.dart';

class EventAdminScreen extends ConsumerStatefulWidget {
  const EventAdminScreen({super.key, required this.id});
  final String id;
  @override
  ConsumerState<EventAdminScreen> createState() => _EventAdminScreenState();
}

class _EventAdminScreenState extends ConsumerState<EventAdminScreen> {
  bool _busy = false;

  Future<void> _run(Future<Object?> Function() fn, {VoidCallback? after}) async {
    final t = ref.read(trProvider);
    setState(() => _busy = true);
    try {
      await fn();
      ref.read(dataVersionProvider.notifier).bump();
      after?.call();
    } catch (e) {
      if (mounted) toast(context, errorText(t, e), tone: Tone.danger);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _transition(String sid, String action, {String? confirm, bool destructive = false}) async {
    final t = ref.read(trProvider);
    if (confirm != null && !await confirmDialog(context, t, t('eventAdmin.$action'), message: confirm, destructive: destructive)) return;
    await _run(() => ref.read(apiProvider).post('/societies/$sid/events/${widget.id}/$action'));
  }

  Future<void> _addVolunteer(String sid) async {
    final t = ref.read(trProvider);
    final m = await showModalBottomSheet<Member>(context: context, isScrollControlled: true, builder: (_) => _MemberPicker(sid: sid));
    if (m == null) return;
    await _run(() => ref.read(apiProvider).post('/societies/$sid/events/${widget.id}/volunteers', {'user_id': m.userId}), after: () => toast(context, t('common.done'), tone: Tone.success));
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    final sid = ref.watch(activeSocietyProvider).societyId;
    if (sid == null) return const Scaffold(body: LoadingView());
    final q = ref.watch(eventProvider((sid: sid, id: widget.id)));
    final report = ref.watch(reportProvider((sid: sid, id: widget.id))).value;
    final vols = ref.watch(volunteersProvider((sid: sid, id: widget.id)));
    return Scaffold(
      appBar: AppBar(title: Text(t('manage.events'))),
      body: AsyncBody<EventT>(
        value: q,
        onRetry: () => ref.invalidate(eventProvider((sid: sid, id: widget.id))),
        builder: (ev) {
          final tone = switch (ev.status) { 'published' => Tone.success, 'draft' => Tone.warning, 'cancelled' => Tone.danger, _ => Tone.neutral };
          return RefreshScroll(onRefresh: () async => ref.read(dataVersionProvider.notifier).bump(), children: [
            AppCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(ev.title, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
                    Text(formatDateTime(ev.startsAt), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                  ])),
                  AppBadge(t('eventAdmin.statusLabel.${ev.status}'), tone: tone),
                ]),
                if (report != null) ...[
                  kGap,
                  Row(children: [
                    _stat(formatInr(report.total('collected_amount')), t('report.collected'), AppColors.success),
                    const SizedBox(width: 20),
                    _stat('${report.total('passes_sold')}', t('report.passesSold'), AppColors.text),
                    const SizedBox(width: 20),
                    _stat('${report.total('pending_count')}', t('common.pending'), report.total('pending_count') > 0 ? AppColors.danger : AppColors.text),
                  ]),
                ],
              ]),
            ),
            Row(children: [
              Expanded(child: AppButton(t('common.edit'), icon: Icons.edit_outlined, variant: 'secondary', onPressed: () => context.push('/manage/event-form?id=${ev.id}'))),
              const SizedBox(width: 8),
              Expanded(child: AppButton(t('eventAdmin.report'), icon: Icons.bar_chart, variant: 'secondary', onPressed: () => context.push('/manage/report/${ev.id}'))),
            ]),
            AppButton(t('eventAdmin.viewEvent'), icon: Icons.visibility_outlined, variant: 'ghost', onPressed: () => context.push('/event/${ev.id}')),
            if (ev.status == 'draft') AppButton(t('eventAdmin.publish'), icon: Icons.rocket_launch, loading: _busy, onPressed: () => _transition(sid, 'publish', confirm: t('eventAdmin.publishConfirm'))),
            if (ev.status == 'published') AppButton(t('eventAdmin.close'), icon: Icons.lock_outline, variant: 'secondary', onPressed: () => _transition(sid, 'close')),
            if (ev.status == 'closed') AppButton(t('eventAdmin.reopen'), icon: Icons.lock_open, variant: 'secondary', onPressed: () => _transition(sid, 'reopen')),
            if (ev.status != 'cancelled' && ev.status != 'draft') AppButton(t('eventAdmin.cancel'), icon: Icons.cancel_outlined, variant: 'danger', onPressed: () => _transition(sid, 'cancel', confirm: t('eventAdmin.cancelConfirm'), destructive: true)),
            if (ev.status == 'draft')
              AppButton(t('eventAdmin.delete'), variant: 'ghost', onPressed: () async {
                if (await confirmDialog(context, t, t('eventAdmin.delete'), message: t('eventAdmin.deleteConfirm'), confirmText: t('common.delete'), destructive: true)) {
                  await _run(() => ref.read(apiProvider).delete('/societies/$sid/events/${ev.id}'), after: () => context.pop());
                }
              }),
            SectionTitle(t('eventAdmin.volunteers'), trailing: ev.status == 'cancelled' ? null : AppButton(t('eventAdmin.addVolunteer'), icon: Icons.person_add_alt, small: true, expand: false, variant: 'secondary', onPressed: () => _addVolunteer(sid))),
            Text(t('eventAdmin.volunteerHelp'), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
            ...vols.when(
              loading: () => [const LoadingView()],
              error: (e, _) => [ErrorView(e, onRetry: () => ref.invalidate(volunteersProvider((sid: sid, id: widget.id))))],
              data: (list) => list.isEmpty
                  ? [InfoBanner(t('eventAdmin.noVolunteers'), tone: Tone.neutral, icon: Icons.people_outline)]
                  : [
                      for (final v in list)
                        AppCard(
                          child: Row(children: [
                            Avatar(v.name ?? v.phone),
                            const SizedBox(width: 12),
                            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              Text(v.name ?? v.phone, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                              Text(t('eventAdmin.expires', {'date': formatDateTime(v.expiresAt)}), style: TextStyle(color: v.active ? AppColors.muted : AppColors.danger, fontSize: 12)),
                            ])),
                            IconButton(icon: const Icon(Icons.cancel, color: AppColors.faint), onPressed: () => _run(() => ref.read(apiProvider).delete('/societies/$sid/events/${ev.id}/volunteers/${v.userId}'))),
                          ]),
                        ),
                    ],
            ),
            AppButton(t('eventAdmin.approvals'), icon: Icons.done_all, variant: 'secondary', onPressed: () => context.push('/manage/approvals')),
          ]);
        },
      ),
    );
  }

  Widget _stat(String v, String l, Color c) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(v, style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: c)),
        Text(l, style: const TextStyle(color: AppColors.muted, fontSize: 12)),
      ]);
}

class _MemberPicker extends ConsumerStatefulWidget {
  const _MemberPicker({required this.sid});
  final String sid;
  @override
  ConsumerState<_MemberPicker> createState() => _MemberPickerState();
}

class _MemberPickerState extends ConsumerState<_MemberPicker> {
  String _q = '';
  List<Member>? _items;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _search();
  }

  Future<void> _search() async {
    try {
      final p = await ref.read(apiProvider).page('/societies/${widget.sid}/members', Member.fromJson, query: {'status': 'active', if (_q.isNotEmpty) 'q': _q}, limit: 30);
      if (mounted) setState(() => _items = p.items);
    } catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + MediaQuery.of(context).viewInsets.bottom),
      child: SizedBox(
        height: MediaQuery.of(context).size.height * 0.65,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(t('eventAdmin.pickMember'), style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
          kGapS,
          AppField(hint: t('members.searchPlaceholder'), onChanged: (v) {
            _q = v.trim();
            _search();
          }),
          kGapS,
          Expanded(
            child: _error != null
                ? ErrorView(_error!, onRetry: _search)
                : _items == null
                    ? const LoadingView()
                    : ListView(children: [
                        for (final m in _items!)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 8),
                            child: AppCard(
                              onTap: () => Navigator.pop(context, m),
                              child: Row(children: [
                                Avatar(m.display),
                                const SizedBox(width: 12),
                                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                  Text(m.display, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                                  Text(m.phone, style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                                ])),
                              ]),
                            ),
                          ),
                      ]),
          ),
        ]),
      ),
    );
  }
}
