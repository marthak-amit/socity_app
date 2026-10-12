import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../core/api.dart';
import '../core/colors.dart';
import '../core/models.dart';
import '../core/utils.dart';
import '../l10n/strings.dart';
import '../state/auth.dart';
import '../state/providers.dart';
import '../ui/widgets.dart';

class JoinScreen extends ConsumerStatefulWidget {
  const JoinScreen({super.key, this.code});
  final String? code;
  @override
  ConsumerState<JoinScreen> createState() => _JoinScreenState();
}

class _JoinScreenState extends ConsumerState<JoinScreen> {
  late final _code = TextEditingController(text: widget.code?.toUpperCase() ?? '');
  final _wing = TextEditingController(), _flat = TextEditingController();
  SocietyBrief? _society;
  String? _error;
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    if (widget.code != null) Future.microtask(() => _lookup(widget.code));
  }

  Future<void> _lookup([String? value]) async {
    final t = ref.read(trProvider);
    final parsed = parseInviteCode(value ?? _code.text);
    if (parsed == null) return setState(() => _error = t('join.invalidCode'));
    setState(() {
      _loading = true;
      _error = null;
      _code.text = parsed;
    });
    try {
      final s = SocietyBrief.fromJson(await ref.read(apiProvider).post('/societies/lookup', {'invite_code': parsed}));
      if (mounted) setState(() => _society = s);
    } catch (e) {
      if (mounted) {
        setState(() {
          _society = null;
          _error = errorText(t, e);
        });
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _request() async {
    final t = ref.read(trProvider);
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final m = Membership.fromJson(await ref.read(apiProvider).post('/societies/join', {
        'invite_code': _code.text,
        'wing': _wing.text.trim().isEmpty ? null : _wing.text.trim(),
        'flat_no': _flat.text.trim().isEmpty ? null : _flat.text.trim(),
      }));
      ref.read(dataVersionProvider.notifier).bump();
      if (!mounted) return;
      if (m.active) {
        await ref.read(authProvider.notifier).setActiveSociety(m.society.id);
        if (mounted) toast(context, t('join.autoApproved', {'name': m.society.name}), tone: Tone.success);
        if (mounted) context.go('/');
      } else {
        toast(context, t('join.sent'), tone: Tone.success);
        context.go('/onboarding?add=1');
      }
    } catch (e) {
      if (mounted) setState(() => _error = errorText(t, e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _scan() async {
    final t = ref.read(trProvider);
    final code = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      builder: (_) => SizedBox(
        height: MediaQuery.of(context).size.height * 0.7,
        child: Stack(children: [
          MobileScanner(
            onDetect: (capture) {
              for (final b in capture.barcodes) {
                final c = parseInviteCode(b.rawValue ?? '');
                if (c != null) {
                  Navigator.of(context).pop(c);
                  return;
                }
              }
            },
          ),
          Positioned(bottom: 24, left: 24, right: 24, child: Text(t('join.scanHelp'), textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600))),
        ]),
      ),
    );
    if (code != null) _lookup(code);
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    return AppScaffold(
      title: t('join.title'),
      body: ListView(padding: kPad, children: [
        if (_society == null) ...[
          AppField(controller: _code, label: t('join.codeLabel'), hint: t('join.codePlaceholder'), textCapitalization: TextCapitalization.characters, maxLength: 40, error: _error, onChanged: (_) => setState(() => _error = null)),
          kGap,
          AppButton(t('join.find'), onPressed: _lookup, loading: _loading),
          kGapS,
          AppButton(t('join.scanQr'), variant: 'secondary', icon: Icons.qr_code_scanner, onPressed: _scan),
        ] else ...[
          AppCard(
            child: Row(children: [
              const Icon(Icons.apartment, size: 28, color: AppColors.primary),
              const SizedBox(width: 12),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(t('join.joining'), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                Text(_society!.name, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
                Text(_society!.city, style: const TextStyle(color: AppColors.muted, fontSize: 12)),
              ])),
            ]),
          ),
          kGap,
          Row(children: [
            Expanded(child: AppField(controller: _wing, label: t('join.wing'), hint: t('join.wingPlaceholder'), textCapitalization: TextCapitalization.characters, maxLength: 20)),
            const SizedBox(width: 12),
            Expanded(child: AppField(controller: _flat, label: t('join.flat'), hint: t('join.flatPlaceholder'), maxLength: 20)),
          ]),
          if (_error != null) ...[kGap, InfoBanner(_error!, tone: Tone.danger)],
          kGap,
          AppButton(t('join.request'), onPressed: _request, loading: _loading),
          AppButton(t('common.back'), variant: 'ghost', onPressed: () => setState(() => _society = null)),
        ],
      ]),
    );
  }
}
