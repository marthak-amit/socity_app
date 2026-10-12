import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api.dart';
import '../../core/colors.dart';
import '../../core/models.dart';
import '../../core/utils.dart';
import '../../l10n/strings.dart';
import '../../state/providers.dart';
import '../../ui/paged.dart';
import '../../ui/widgets.dart';

List<Widget> flagBadges(Tr t, List<String> flags, {bool hasUtr = true}) =>
    [for (final f in flags) if (f != 'missing_utr' || !hasUtr) AppBadge(t('approvals.flag.$f'), tone: Tone.warning, icon: Icons.flag)];

class ApprovalsScreen extends ConsumerStatefulWidget {
  const ApprovalsScreen({super.key});
  @override
  ConsumerState<ApprovalsScreen> createState() => _ApprovalsScreenState();
}

class _ApprovalsScreenState extends ConsumerState<ApprovalsScreen> {
  String _tab = 'pending';
  final Set<String> _selected = {};
  bool _busy = false;

  Future<void> _bulk(String sid) async {
    final t = ref.read(trProvider);
    if (!await confirmDialog(context, t, t('approvals.bulkApprove', {'n': _selected.length}), message: t('approvals.approveConfirm'), confirmText: t('common.approve'))) return;
    setState(() => _busy = true);
    try {
      final r = await ref.read(apiProvider).post('/societies/$sid/orders/bulk-approve', {'order_ids': _selected.toList()});
      final approved = (r['approved'] as List).length, skipped = (r['skipped'] as List).length;
      if (mounted) toast(context, '${t('approvals.approvedN', {'n': approved})}${skipped > 0 ? ' · ${t('approvals.skipped', {'n': skipped})}' : ''}', tone: skipped > 0 ? Tone.neutral : Tone.success);
      setState(_selected.clear);
      ref.read(dataVersionProvider.notifier).bump();
    } catch (e) {
      if (mounted) toast(context, errorText(t, e), tone: Tone.danger);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    final sid = ref.watch(activeSocietyProvider).societyId;
    if (sid == null) return const Scaffold(body: LoadingView());
    final summary = ref.watch(orderSummaryProvider(sid)).value;
    return Scaffold(
      appBar: AppBar(title: Text(t('approvals.title'))),
      body: Stack(children: [
        PagedListView<Order>(
          key: ValueKey('approvals-$_tab'),
          path: '/societies/$sid/orders',
          query: {'status': _tab, if (_tab == 'pending') 'submitted': true},
          parse: Order.fromJson,
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 120),
          empty: EmptyState(icon: Icons.done_all, title: t('approvals.empty'), subtitle: t('approvals.emptySub')),
          header: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            SegmentedTabs<String>(
              value: _tab,
              onChanged: (v) => setState(() {
                _tab = v;
                _selected.clear();
              }),
              options: [('pending', t('approvals.pending'), summary?.pending), ('approved', t('approvals.approved'), null), ('rejected', t('approvals.rejected'), null)],
            ),
            if (_tab == 'pending') Padding(padding: const EdgeInsets.only(top: 6), child: Text(t('approvals.selectHint'), style: const TextStyle(color: AppColors.muted, fontSize: 12))),
          ]),
          itemBuilder: (_, o, _) {
            void toggle() {
              if (!o.pending) return;
              setState(() => _selected.contains(o.id) ? _selected.remove(o.id) : _selected.add(o.id));
            }

            return AppCard(
              selected: _selected.contains(o.id),
              onLongPress: toggle,
              onTap: () => _selected.isNotEmpty ? toggle() : context.push('/manage/approvals/${o.id}'),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(o.member?.display ?? '', overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                    Text('${o.member?.flat.isEmpty ?? true ? '—' : o.member!.flat} · ${o.eventTitle}', style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                  ])),
                  Text(formatInr(o.totalAmount), style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: AppColors.primary)),
                ]),
                const SizedBox(height: 4),
                Text(o.items.map((i) => '${i.qty}× ${i.tierName}').join(', '), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                const SizedBox(height: 6),
                Wrap(spacing: 6, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
                  AppBadge(o.utr ?? t('approvals.flag.missing_utr'), icon: Icons.receipt_long_outlined),
                  ...flagBadges(t, o.flags, hasUtr: o.utr != null),
                  if (o.hasScreenshot) AppBadge(t('approvals.proof'), tone: Tone.info, icon: Icons.image),
                  if (_selected.contains(o.id)) const Icon(Icons.check_circle, size: 20, color: AppColors.primary),
                ]),
                const SizedBox(height: 4),
                Text(formatDateTime(o.paymentSubmittedAt ?? o.createdAt), style: const TextStyle(color: AppColors.faint, fontSize: 12)),
              ]),
            );
          },
        ),
        if (_selected.isNotEmpty)
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            child: Container(
              padding: const EdgeInsets.all(16),
              decoration: const BoxDecoration(color: AppColors.card, border: Border(top: BorderSide(color: AppColors.border))),
              child: SafeArea(
                top: false,
                child: Row(children: [
                  Expanded(child: AppButton(t('common.cancel'), variant: 'secondary', onPressed: () => setState(_selected.clear))),
                  const SizedBox(width: 8),
                  Expanded(flex: 2, child: AppButton(t('approvals.bulkApprove', {'n': _selected.length}), variant: 'success', onPressed: () => _bulk(sid), loading: _busy)),
                ]),
              ),
            ),
          ),
      ]),
    );
  }
}

class ApprovalDetailScreen extends ConsumerStatefulWidget {
  const ApprovalDetailScreen({super.key, required this.id});
  final String id;
  @override
  ConsumerState<ApprovalDetailScreen> createState() => _ApprovalDetailScreenState();
}

class _ApprovalDetailScreenState extends ConsumerState<ApprovalDetailScreen> {
  bool _busy = false;

  Future<void> _approve(Order o, String sid) async {
    final t = ref.read(trProvider);
    if (!await confirmDialog(context, t, o.flags.isNotEmpty ? t('approvals.includeFlagged') : t('common.approve'), message: t('approvals.approveConfirm'), confirmText: t('common.approve'))) return;
    await _run(() => ref.read(apiProvider).post('/societies/$sid/orders/${o.id}/approve'), t('common.approved'));
  }

  Future<void> _reject(Order o, String sid) async {
    final t = ref.read(trProvider);
    final reason = await showModalBottomSheet<String>(context: context, isScrollControlled: true, builder: (_) => _RejectSheet());
    if (reason == null) return;
    await _run(() => ref.read(apiProvider).post('/societies/$sid/orders/${o.id}/reject', {'reason': reason}), t('common.rejected'));
  }

  Future<void> _run(Future<Object?> Function() fn, String okMsg) async {
    final t = ref.read(trProvider);
    setState(() => _busy = true);
    try {
      await fn();
      ref.read(dataVersionProvider.notifier).bump();
      if (mounted) {
        toast(context, okMsg, tone: Tone.success);
        context.pop();
      }
    } catch (e) {
      if (mounted) toast(context, errorText(t, e), tone: Tone.danger);
      ref.read(dataVersionProvider.notifier).bump();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    final sid = ref.watch(activeSocietyProvider).societyId;
    if (sid == null) return const Scaffold(body: LoadingView());
    final q = ref.watch(orderProvider((sid: sid, id: widget.id)));
    return Scaffold(
      appBar: AppBar(title: Text(t('approvals.title'))),
      body: AsyncBody<Order>(
        value: q,
        onRetry: () => ref.invalidate(orderProvider((sid: sid, id: widget.id))),
        builder: (o) {
          final mismatch = o.paidAmount != null && o.paidAmount != o.totalAmount;
          return RefreshScroll(onRefresh: () async => ref.read(dataVersionProvider.notifier).bump(), children: [
            for (final f in o.flags) InfoBanner('${t('approvals.flag.$f')} — ${t('approvals.flagHelp.$f')}', icon: Icons.flag),
            AppCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(o.member?.display ?? '', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
                    Text('${o.member?.phone ?? ''} · ${o.member?.flat ?? ''}', style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                  ])),
                  AppBadge(t('common.${o.status}'), tone: o.status == 'approved' ? Tone.success : (o.pending ? Tone.warning : Tone.danger)),
                ]),
                const Divider(),
                Text('${o.eventTitle} · ${o.refCode}', style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                for (final it in o.items)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Row(children: [Expanded(child: Text('${it.qty} × ${it.tierName}')), Text(formatInr(it.qty * it.unitPrice))]),
                      Text(it.holders.map((h) => '${h.name}${h.type == 'guest' ? ' (G)' : ''}').join(', '), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                    ]),
                  ),
                const Divider(),
                Row(children: [
                  Expanded(child: Text(t('approvals.amount'), style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700))),
                  Text(formatInr(o.totalAmount), style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: AppColors.primary)),
                ]),
                if (o.paidAmount != null)
                  Row(children: [
                    Expanded(child: Text(t('approvals.claimed'), style: const TextStyle(color: AppColors.muted, fontSize: 12))),
                    Text(formatInr(o.paidAmount!), style: TextStyle(fontWeight: FontWeight.w600, color: mismatch ? AppColors.danger : AppColors.success)),
                  ]),
                const SizedBox(height: 4),
                Row(children: [
                  Expanded(child: Text(t('approvals.utr'), style: const TextStyle(color: AppColors.muted, fontSize: 12))),
                  SelectableText(o.utr ?? '—', style: const TextStyle(fontWeight: FontWeight.w600)),
                ]),
                if (o.paymentSubmittedAt != null) Text(formatDateTime(o.paymentSubmittedAt!), style: const TextStyle(color: AppColors.faint, fontSize: 12)),
                if (o.rejectReason != null) ...[kGapS, InfoBanner(o.rejectReason!, tone: Tone.danger)],
              ]),
            ),
            SectionTitle(t('approvals.proof')),
            if (o.screenshotUrl != null)
              GestureDetector(
                onTap: () => Navigator.of(context).push(MaterialPageRoute(
                  fullscreenDialog: true,
                  builder: (_) => Scaffold(backgroundColor: Colors.black, appBar: AppBar(backgroundColor: Colors.black, foregroundColor: Colors.white), body: InteractiveViewer(child: Center(child: CachedNetworkImage(imageUrl: o.screenshotUrl!)))),
                )),
                child: ClipRRect(borderRadius: BorderRadius.circular(12), child: CachedNetworkImage(imageUrl: o.screenshotUrl!, height: 360, width: double.infinity, fit: BoxFit.contain, errorWidget: (_, _, _) => InfoBanner(t('approvals.noScreenshot'), tone: Tone.neutral))),
              )
            else
              InfoBanner(t('approvals.noScreenshot'), tone: Tone.neutral, icon: Icons.image_outlined),
            if (o.pending) ...[
              if (!o.submitted) InfoBanner(t('errors.payment_not_submitted'), tone: Tone.info),
              Row(children: [
                Expanded(child: AppButton(t('common.reject'), variant: 'danger', icon: Icons.close, onPressed: _busy ? null : () => _reject(o, sid))),
                const SizedBox(width: 8),
                Expanded(child: AppButton(o.flags.isNotEmpty ? t('approvals.includeFlagged') : t('common.approve'), variant: 'success', icon: Icons.check, loading: _busy, onPressed: o.submitted ? () => _approve(o, sid) : null)),
              ]),
            ],
          ]);
        },
      ),
    );
  }
}

class _RejectSheet extends ConsumerStatefulWidget {
  @override
  ConsumerState<_RejectSheet> createState() => _RejectSheetState();
}

class _RejectSheetState extends ConsumerState<_RejectSheet> {
  final _c = TextEditingController();
  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    final quick = [t('approvals.quickReasons.notFound'), t('approvals.quickReasons.wrongAmount'), t('approvals.quickReasons.badProof'), t('approvals.quickReasons.duplicate')];
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + MediaQuery.of(context).viewInsets.bottom),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Text(t('approvals.rejectTitle'), style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
        kGap,
        Wrap(spacing: 8, runSpacing: 8, children: [for (final r in quick) TagChip(r, selected: _c.text == r, onTap: () => setState(() => _c.text = r))]),
        kGap,
        AppField(controller: _c, label: t('approvals.rejectReason'), maxLength: 300, onChanged: (_) => setState(() {})),
        kGap,
        Row(children: [
          Expanded(child: AppButton(t('common.cancel'), variant: 'secondary', onPressed: () => Navigator.pop(context))),
          const SizedBox(width: 8),
          Expanded(child: AppButton(t('common.reject'), variant: 'danger', onPressed: _c.text.trim().length < 3 ? null : () => Navigator.pop(context, _c.text.trim()))),
        ]),
      ]),
    );
  }
}
