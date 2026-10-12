import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/api.dart';
import '../core/colors.dart';
import '../core/models.dart';
import '../core/utils.dart';
import '../l10n/strings.dart';
import '../state/providers.dart';
import '../ui/widgets.dart';

class BuyScreen extends ConsumerStatefulWidget {
  const BuyScreen({super.key, required this.eventId});
  final String eventId;
  @override
  ConsumerState<BuyScreen> createState() => _BuyScreenState();
}

class _BuyScreenState extends ConsumerState<BuyScreen> {
  final Map<String, List<Holder>> _sel = {}; // tier id → one holder per pass
  final Map<String, List<TextEditingController>> _ctrls = {};
  String? _error;
  bool _loading = false;

  int get _count => _sel.values.fold(0, (n, h) => n + h.length);

  void _setQty(Tier tier, int delta, {String? buyerName}) {
    final max = tier.perUserLimit < tier.remaining ? tier.perUserLimit : tier.remaining;
    final cur = _sel[tier.id] ?? <Holder>[];
    final n = (cur.length + delta).clamp(0, max);
    if (n == cur.length) return;
    setState(() {
      _error = null;
      final isFirstEver = _count == 0 && cur.isEmpty;
      final holders = cur.take(n).toList();
      final ctrls = (_ctrls[tier.id] ?? []).take(n).toList();
      while (holders.length < n) {
        final first = isFirstEver && holders.isEmpty;
        final h = Holder(name: first ? (buyerName ?? '') : '', type: first || !tier.allowGuests ? 'member' : 'guest');
        holders.add(h);
        ctrls.add(TextEditingController(text: h.name));
      }
      for (final c in (_ctrls[tier.id] ?? []).skip(n)) {
        c.dispose();
      }
      if (n == 0) {
        _sel.remove(tier.id);
        _ctrls.remove(tier.id);
      } else {
        _sel[tier.id] = holders;
        _ctrls[tier.id] = ctrls;
      }
    });
  }

  @override
  void dispose() {
    for (final l in _ctrls.values) {
      for (final c in l) {
        c.dispose();
      }
    }
    super.dispose();
  }

  Future<void> _submit(EventT ev) async {
    final t = ref.read(trProvider);
    final sid = ref.read(activeSocietyProvider).societyId!;
    if (_count == 0) return setState(() => _error = t('buy.pickAtLeastOne'));
    for (final e in _sel.entries) {
      for (var i = 0; i < e.value.length; i++) {
        e.value[i].name = _ctrls[e.key]![i].text;
      }
    }
    if (_sel.values.any((hs) => hs.any((h) => h.name.trim().isEmpty))) return setState(() => _error = t('buy.nameRequired'));
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final order = Order.fromJson(await ref.read(apiProvider).post('/societies/$sid/events/${ev.id}/orders', {
        'items': [
          for (final e in _sel.entries) {'tier_id': e.key, 'qty': e.value.length, 'holders': e.value.map((h) => h.toJson()).toList()},
        ],
      }));
      ref.read(dataVersionProvider.notifier).bump();
      if (!mounted) return;
      if (order.status == 'approved') {
        toast(context, t('buy.freeDone'), tone: Tone.success);
        context.go('/?tab=passes');
      } else {
        context.pushReplacement('/order/${order.id}');
      }
    } catch (e) {
      if (mounted) setState(() => _error = errorText(t, e));
      ref.read(dataVersionProvider.notifier).bump();
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    final active = ref.watch(activeSocietyProvider);
    final sid = active.societyId;
    if (sid == null) return const Scaffold(body: LoadingView());
    final q = ref.watch(eventProvider((sid: sid, id: widget.eventId)));
    return Scaffold(
      appBar: AppBar(title: Text(t('buy.title'))),
      body: AsyncBody<EventT>(
        value: q,
        onRetry: () => ref.invalidate(eventProvider((sid: sid, id: widget.eventId))),
        builder: (ev) {
          final total = ev.tiers.fold<int>(0, (s, x) => s + x.price * (_sel[x.id]?.length ?? 0));
          return Column(children: [
            Expanded(
              child: ListView(padding: kPad, children: [
                Text(ev.title, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
                kGap,
                for (final tier in ev.tiers) ...[
                  _tierCard(tier, t, active.user?.name),
                  kGapS,
                ],
                if (_error != null) InfoBanner(_error!, tone: Tone.danger),
              ]),
            ),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: const BoxDecoration(color: AppColors.card, border: Border(top: BorderSide(color: AppColors.border))),
              child: SafeArea(
                top: false,
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                    Text(t('buy.total'), style: const TextStyle(color: AppColors.muted)),
                    Text(formatInr(total), style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
                  ]),
                  kGapS,
                  AppButton(total == 0 && _count > 0 ? t('buy.freeConfirm') : t('buy.continueToPay'), onPressed: _count == 0 ? null : () => _submit(ev), loading: _loading),
                ]),
              ),
            ),
          ]);
        },
      ),
    );
  }

  Widget _tierCard(Tier tier, Tr t, String? buyer) {
    final held = _sel[tier.id] ?? const <Holder>[];
    final max = tier.perUserLimit < tier.remaining ? tier.perUserLimit : tier.remaining;
    return Opacity(
      opacity: tier.remaining == 0 ? 0.55 : 1,
      child: AppCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(tier.name, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
              Text('${priceLabel(tier.price, free: t('common.free'))} · ${tier.remaining == 0 ? t('event.soldOut') : t('event.left', {'n': tier.remaining})}', style: const TextStyle(color: AppColors.muted, fontSize: 12)),
            ])),
            _stepper(Icons.remove, held.isEmpty ? null : () => _setQty(tier, -1, buyerName: buyer), 'Decrease ${tier.name}'),
            SizedBox(width: 32, child: Text('${held.length}', textAlign: TextAlign.center, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700))),
            _stepper(Icons.add, held.length >= max ? null : () => _setQty(tier, 1, buyerName: buyer), 'Increase ${tier.name}'),
          ]),
          if (held.length >= max && max > 0) Text('${t('buy.maxReached')} ($max)', style: const TextStyle(color: AppColors.warning, fontSize: 12)),
          if (held.isNotEmpty) ...[
            kGap,
            Text(t('buy.holders'), style: const TextStyle(color: AppColors.muted, fontSize: 13, fontWeight: FontWeight.w500)),
            kGapS,
            for (var i = 0; i < held.length; i++) ...[
              AppField(controller: _ctrls[tier.id]![i], hint: '${t('buy.holderName')} #${i + 1}', maxLength: 120, textCapitalization: TextCapitalization.words),
              if (tier.allowGuests)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Row(children: [
                    TagChip(t('buy.member'), icon: Icons.home_outlined, selected: held[i].type == 'member', onTap: () => setState(() => held[i].type = 'member')),
                    const SizedBox(width: 8),
                    TagChip(t('buy.guest'), icon: Icons.person_add_alt, selected: held[i].type == 'guest', onTap: () => setState(() => held[i].type = 'guest')),
                  ]),
                ),
              kGapS,
            ],
          ],
        ]),
      ),
    );
  }

  Widget _stepper(IconData icon, VoidCallback? onTap, String label) => Semantics(
        button: true,
        label: label,
        child: InkResponse(
          onTap: onTap,
          child: Opacity(
            opacity: onTap == null ? 0.35 : 1,
            child: Container(
              width: 36,
              height: 36,
              decoration: const BoxDecoration(color: AppColors.primarySoft, shape: BoxShape.circle),
              child: Icon(icon, size: 20, color: AppColors.primary),
            ),
          ),
        ),
      );
}
