import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/api.dart';
import '../../core/colors.dart';
import '../../core/models.dart';
import '../../core/utils.dart';
import '../../l10n/strings.dart';
import '../../state/auth.dart';
import '../../state/providers.dart';
import '../../ui/widgets.dart';

class SocietySettingsScreen extends ConsumerStatefulWidget {
  const SocietySettingsScreen({super.key});
  @override
  ConsumerState<SocietySettingsScreen> createState() => _SocietySettingsScreenState();
}

class _SocietySettingsScreenState extends ConsumerState<SocietySettingsScreen> {
  final _c = {for (final k in ['name', 'city', 'address', 'upi_id', 'upi_name']) k: TextEditingController()};
  final _confirm = TextEditingController();
  Uint8List? _logo;
  String? _logoMime, _error;
  bool _seeded = false, _busy = false;

  void _seed(Society s) {
    if (_seeded) return;
    _seeded = true;
    _c['name']!.text = s.name;
    _c['city']!.text = s.city;
    _c['address']!.text = s.address ?? '';
    _c['upi_id']!.text = s.upiId ?? '';
    _c['upi_name']!.text = s.upiName ?? '';
  }

  Future<void> _save(Society s) async {
    final t = ref.read(trProvider);
    final upi = _c['upi_id']!.text.trim();
    if (upi.isNotEmpty && !isValidUpiId(upi)) return setState(() => _error = t('createSociety.invalidUpi'));
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final api = ref.read(apiProvider);
      final logoId = _logo == null ? null : await api.uploadImage(societyId: s.id, purpose: 'logo', bytes: _logo!, mime: _logoMime);
      await api.patch('/societies/${s.id}', {
        'name': _c['name']!.text.trim(),
        'city': _c['city']!.text.trim(),
        'address': _c['address']!.text.trim().isEmpty ? null : _c['address']!.text.trim(),
        'upi_id': upi,
        'upi_name': _c['upi_name']!.text.trim().isEmpty ? null : _c['upi_name']!.text.trim(),
        'logo_upload_id': logoId,
      });
      _logo = null;
      ref.read(dataVersionProvider.notifier).bump();
      if (mounted) toast(context, t('settings.saved'), tone: Tone.success);
    } catch (e) {
      if (mounted) setState(() => _error = errorText(t, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _delete(Society s) async {
    final t = ref.read(trProvider);
    if (!await confirmDialog(context, t, t('manage.deleteSociety'), message: t('manage.deleteWarn'), confirmText: t('common.delete'), destructive: true)) return;
    try {
      await ref.read(apiProvider).delete('/societies/${s.id}', {'confirm_name': _confirm.text.trim()});
      await ref.read(authProvider.notifier).setActiveSociety(null);
      ref.read(dataVersionProvider.notifier).bump();
      if (mounted) {
        toast(context, t('manage.deleted'));
        context.go('/');
      }
    } catch (e) {
      if (mounted) toast(context, errorText(t, e), tone: Tone.danger);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    final active = ref.watch(activeSocietyProvider);
    final sid = active.societyId;
    if (sid == null) return const Scaffold(body: LoadingView());
    final q = ref.watch(societyDetailProvider(sid));
    return AppScaffold(
      title: t('manage.settings'),
      body: AsyncBody<Society>(
        value: q,
        onRetry: () => ref.invalidate(societyDetailProvider(sid)),
        builder: (s) {
          _seed(s);
          return ListView(padding: kPad, children: [
            Center(
              child: GestureDetector(
                onTap: () async {
                  final f = await ImagePicker().pickImage(source: ImageSource.gallery, imageQuality: 85);
                  if (f == null) return;
                  final b = await f.readAsBytes();
                  setState(() {
                    _logo = b;
                    _logoMime = f.mimeType;
                  });
                },
                child: Column(children: [
                  Container(
                    width: 96,
                    height: 96,
                    clipBehavior: Clip.antiAlias,
                    decoration: BoxDecoration(color: AppColors.primarySoft, borderRadius: BorderRadius.circular(24)),
                    child: _logo != null ? Image.memory(_logo!, fit: BoxFit.cover) : (s.logoUrl != null ? Image.network(s.logoUrl!, fit: BoxFit.cover) : const Icon(Icons.apartment, size: 40, color: AppColors.primary)),
                  ),
                  const SizedBox(height: 4),
                  Text(t('settings.logo'), style: const TextStyle(color: AppColors.primary, fontSize: 12)),
                ]),
              ),
            ),
            kGap,
            AppField(controller: _c['name'], label: t('settings.societyName')),
            kGap,
            AppField(controller: _c['city'], label: t('createSociety.city')),
            kGap,
            AppField(controller: _c['address'], label: t('createSociety.address'), maxLines: 3),
            const SectionTitle('UPI'),
            kGap,
            AppField(controller: _c['upi_id'], label: t('createSociety.upiId'), helper: t('createSociety.upiHelp')),
            kGap,
            AppField(controller: _c['upi_name'], label: t('createSociety.upiName')),
            if (_error != null) ...[kGap, InfoBanner(_error!, tone: Tone.danger)],
            kGap,
            AppButton(t('common.save'), onPressed: () => _save(s), loading: _busy),
            if (active.role == Role.owner) ...[
              SectionTitle(t('manage.dangerZone')),
              kGapS,
              AppCard(
                borderColor: AppColors.danger,
                child: StatefulBuilder(
                  builder: (context, setLocal) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(t('manage.deleteWarn'), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                    kGapS,
                    AppField(controller: _confirm, label: t('manage.typeName'), hint: s.name, onChanged: (_) => setLocal(() {})),
                    kGapS,
                    AppButton(t('manage.deleteSociety'), variant: 'danger', onPressed: _confirm.text.trim() == s.name ? () => _delete(s) : null),
                  ]),
                ),
              ),
            ],
          ]);
        },
      ),
    );
  }
}
