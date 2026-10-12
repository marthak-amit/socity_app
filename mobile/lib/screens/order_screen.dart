import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/api.dart';
import '../core/colors.dart';
import '../core/models.dart';
import '../core/utils.dart';
import '../l10n/strings.dart';
import '../state/providers.dart';
import '../ui/widgets.dart';

class OrderScreen extends ConsumerStatefulWidget {
  const OrderScreen({super.key, required this.id});
  final String id;
  @override
  ConsumerState<OrderScreen> createState() => _OrderScreenState();
}

class _OrderScreenState extends ConsumerState<OrderScreen> {
  final _utr = TextEditingController(), _paid = TextEditingController();
  Uint8List? _shot;
  String? _shotMime, _error;
  bool _busy = false, _seeded = false;
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    // While waiting for an admin, keep the status fresh.
    _poll = Timer.periodic(const Duration(seconds: 20), (_) => mounted ? ref.read(dataVersionProvider.notifier).bump() : null);
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  void _seed(Order o) {
    if (_seeded) return;
    _seeded = true;
    _utr.text = o.utr ?? '';
    _paid.text = '${o.paidAmount ?? o.totalAmount}';
  }

  Future<void> _payViaUpi(Order o) async {
    final t = ref.read(trProvider);
    final uri = o.payment?.upiUri;
    if (uri == null) return;
    try {
      if (!await launchUrl(Uri.parse(uri), mode: LaunchMode.externalApplication)) throw 'no app';
    } catch (_) {
      if (mounted) toast(context, t('order.noUpiApp'));
    }
  }

  Future<void> _pickShot() async {
    final f = await ImagePicker().pickImage(source: ImageSource.gallery, imageQuality: 85);
    if (f == null) return;
    final bytes = await f.readAsBytes();
    setState(() {
      _shot = bytes;
      _shotMime = f.mimeType;
      _error = null;
    });
  }

  Future<void> _submit(Order o, String sid) async {
    final t = ref.read(trProvider);
    final hasUtr = _utr.text.isNotEmpty;
    if (hasUtr && !isValidUtr(_utr.text)) return setState(() => _error = t('order.invalidUtr'));
    if (!hasUtr && _shot == null && !o.hasScreenshot) return setState(() => _error = t('order.proofRequired'));
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final api = ref.read(apiProvider);
      final uploadId = _shot == null ? null : await api.uploadImage(societyId: sid, purpose: 'screenshot', bytes: _shot!, mime: _shotMime);
      await api.post('/societies/$sid/orders/${o.id}/payment', {
        'screenshot_upload_id': uploadId,
        'utr': hasUtr ? _utr.text : null,
        'paid_amount': _paid.text.isEmpty ? null : int.tryParse(_paid.text),
      });
      _shot = null;
      ref.read(dataVersionProvider.notifier).bump();
      if (mounted) toast(context, t('order.submitted'), tone: Tone.success);
    } catch (e) {
      if (mounted) setState(() => _error = errorText(t, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _cancel(Order o, String sid) async {
    final t = ref.read(trProvider);
    if (!await confirmDialog(context, t, t('order.cancelOrder'), message: t('order.cancelConfirm'), confirmText: t('common.yes'), destructive: true)) return;
    try {
      await ref.read(apiProvider).post('/societies/$sid/orders/${o.id}/cancel');
      ref.read(dataVersionProvider.notifier).bump();
      if (mounted) context.pop();
    } catch (e) {
      if (mounted) toast(context, errorText(t, e), tone: Tone.danger);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    final sid = ref.watch(activeSocietyProvider).societyId;
    if (sid == null) return const Scaffold(body: LoadingView());
    final q = ref.watch(orderProvider((sid: sid, id: widget.id)));
    return Scaffold(
      appBar: AppBar(title: Text(t('order.status'))),
      body: AsyncBody<Order>(
        value: q,
        onRetry: () => ref.invalidate(orderProvider((sid: sid, id: widget.id))),
        builder: (o) {
          _seed(o);
          final submitted = o.submitted;
          final expired = o.pending && !submitted && o.expiresAt != null && o.expiresAt!.isBefore(DateTime.now());
          final tone = o.status == 'approved' ? Tone.success : (o.pending ? Tone.warning : Tone.danger);
          return RefreshScroll(onRefresh: () async => ref.read(dataVersionProvider.notifier).bump(), children: [
            AppCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(t('order.title', {'ref': o.refCode}), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                    Text(o.eventTitle, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
                  ])),
                  AppBadge(o.pending ? (submitted ? t('order.inReview') : t('order.awaitingPayment')) : t('common.${o.status}'), tone: tone),
                ]),
                const Divider(),
                for (final it in o.items)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Row(children: [Expanded(child: Text('${it.qty} × ${it.tierName}')), Text(formatInr(it.qty * it.unitPrice))]),
                  ),
                const Divider(),
                Row(children: [
                  Expanded(child: Text(t('buy.total'), style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700))),
                  Text(formatInr(o.totalAmount), style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: AppColors.primary)),
                ]),
                Padding(padding: const EdgeInsets.only(top: 4), child: Text(t('order.placedOn', {'date': formatDateTime(o.createdAt)}), style: const TextStyle(color: AppColors.faint, fontSize: 12))),
              ]),
            ),
            if (o.status == 'approved') ...[
              InfoBanner('${t('order.approvedTitle')} ${t('order.approvedBody')}', tone: Tone.success, icon: Icons.check_circle),
              AppButton(t('order.viewPasses'), icon: Icons.confirmation_number, onPressed: () => context.go('/?tab=passes')),
            ],
            if (o.status == 'rejected') ...[
              InfoBanner('${t('order.rejectedTitle')}${o.rejectReason != null ? ' — ${o.rejectReason}' : ''}', tone: Tone.danger, icon: Icons.cancel),
              AppButton(t('order.tryAgain'), variant: 'secondary', onPressed: () => context.pushReplacement('/event/${o.eventId}')),
            ],
            if (o.status == 'cancelled') InfoBanner(o.rejectReason == 'expired' ? t('order.expired') : t('common.cancelled'), tone: Tone.neutral, icon: Icons.remove_circle_outline),
            if (o.pending && !expired && o.payment != null) ...[
              if (!submitted && o.expiresAt != null) InfoBanner(t('order.expiresIn', {'time': formatCountdown(o.expiresAt!)}), icon: Icons.hourglass_bottom),
              SectionTitle(t('order.step1')),
              AppCard(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(formatInr(o.payment!.amount), style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w800, color: AppColors.primary)),
                  const Divider(),
                  Row(children: [
                    Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(t('order.upiId'), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                      SelectableText(o.payment!.upiId ?? '', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
                    ])),
                    AppButton(t('common.copy'), icon: Icons.copy, small: true, expand: false, variant: 'secondary', onPressed: () async {
                      await Clipboard.setData(ClipboardData(text: o.payment!.upiId ?? ''));
                      if (context.mounted) toast(context, t('common.copied'));
                    }),
                  ]),
                  const SizedBox(height: 8),
                  Text('${t('order.payee')}: ${o.payment!.payeeName ?? ''}', style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                  Text('${t('order.note')}: ${o.payment!.note ?? ''}', style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                  kGap,
                  AppButton(t('order.payViaUpi'), icon: Icons.phone_android, onPressed: o.payment!.upiUri == null ? null : () => _payViaUpi(o)),
                ]),
              ),
              SectionTitle(t('order.step2')),
              AppCard(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  if (submitted) ...[InfoBanner('${t('order.inReview')} — ${t('order.waitingNote')}', tone: Tone.info, icon: Icons.schedule), kGap],
                  Text(t('order.screenshot'), style: const TextStyle(color: AppColors.muted, fontSize: 13)),
                  kGapS,
                  if (_shot != null) ClipRRect(borderRadius: BorderRadius.circular(12), child: Image.memory(_shot!, height: 220, width: double.infinity, fit: BoxFit.contain))
                  else if (o.hasScreenshot) Row(children: [const Icon(Icons.check_circle, size: 20, color: AppColors.success), const SizedBox(width: 6), Text('${t('order.screenshot')} ✓', style: const TextStyle(color: AppColors.success))]),
                  kGapS,
                  AppButton(_shot != null || o.hasScreenshot ? t('order.changeScreenshot') : t('order.pickScreenshot'), icon: Icons.image_outlined, variant: 'secondary', onPressed: _pickShot),
                  kGap,
                  AppField(controller: _utr, label: t('order.utr'), hint: '402611223344', helper: t('order.utrHelp'), keyboardType: TextInputType.number, maxLength: 14, onChanged: (v) {
                    final s = sanitizeUtr(v);
                    if (s != v) _utr.value = TextEditingValue(text: s, selection: TextSelection.collapsed(offset: s.length));
                    setState(() => _error = null);
                  }),
                  kGap,
                  AppField(controller: _paid, label: t('order.amountPaid'), keyboardType: TextInputType.number),
                  if (_error != null) ...[kGap, InfoBanner(_error!, tone: Tone.danger)],
                  kGap,
                  AppButton(submitted ? t('order.resubmit') : t('order.submitProof'), onPressed: () => _submit(o, sid), loading: _busy),
                ]),
              ),
              AppButton(t('order.cancelOrder'), variant: 'ghost', onPressed: () => _cancel(o, sid)),
            ],
            if (expired) InfoBanner(t('order.expired'), tone: Tone.danger),
          ]);
        },
      ),
    );
  }
}
