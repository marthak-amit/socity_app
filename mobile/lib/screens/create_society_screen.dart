import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/api.dart';
import '../core/models.dart';
import '../core/utils.dart';
import '../l10n/strings.dart';
import '../state/auth.dart';
import '../state/providers.dart';
import '../ui/widgets.dart';

class CreateSocietyScreen extends ConsumerStatefulWidget {
  const CreateSocietyScreen({super.key});
  @override
  ConsumerState<CreateSocietyScreen> createState() => _CreateSocietyScreenState();
}

class _CreateSocietyScreenState extends ConsumerState<CreateSocietyScreen> {
  final _c = {for (final k in ['name', 'city', 'address', 'upi_id', 'upi_name', 'wing', 'flat_no']) k: TextEditingController()};
  String? _error;
  bool _loading = false;

  String? _v(String k) => _c[k]!.text.trim().isEmpty ? null : _c[k]!.text.trim();

  Future<void> _submit() async {
    final t = ref.read(trProvider);
    if (_c['name']!.text.trim().length < 2 || _c['city']!.text.trim().length < 2) return setState(() => _error = t('common.required'));
    if (_v('upi_id') != null && !isValidUpiId(_v('upi_id')!)) return setState(() => _error = t('createSociety.invalidUpi'));
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final s = Society.fromJson(await ref.read(apiProvider).post('/societies', {for (final k in _c.keys) k: _v(k)}));
      await ref.read(authProvider.notifier).setActiveSociety(s.id);
      ref.read(dataVersionProvider.notifier).bump();
      if (!mounted) return;
      toast(context, t('createSociety.created'), tone: Tone.success);
      context.go('/');
      context.push('/manage/invite');
    } catch (e) {
      if (mounted) setState(() => _error = errorText(t, e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    return AppScaffold(
      title: t('createSociety.title'),
      body: ListView(padding: kPad, children: [
        AppField(controller: _c['name'], label: t('createSociety.name'), textCapitalization: TextCapitalization.words),
        kGap,
        AppField(controller: _c['city'], label: t('createSociety.city'), textCapitalization: TextCapitalization.words),
        kGap,
        AppField(controller: _c['address'], label: t('createSociety.address'), maxLines: 3),
        const SectionTitle('UPI'),
        kGap,
        AppField(controller: _c['upi_id'], label: t('createSociety.upiId'), hint: 'society@okhdfc', helper: t('createSociety.upiHelp')),
        kGap,
        AppField(controller: _c['upi_name'], label: t('createSociety.upiName')),
        kGap,
        Row(children: [
          Expanded(child: AppField(controller: _c['wing'], label: t('createSociety.wing'))),
          const SizedBox(width: 12),
          Expanded(child: AppField(controller: _c['flat_no'], label: t('createSociety.flat'))),
        ]),
        if (_error != null) ...[kGap, InfoBanner(_error!, tone: Tone.danger)],
        kGap,
        AppButton(t('createSociety.create'), onPressed: _submit, loading: _loading),
      ]),
    );
  }
}
