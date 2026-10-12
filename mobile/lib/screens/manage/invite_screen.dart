import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:qr_flutter/qr_flutter.dart';
import 'package:share_plus/share_plus.dart';

import '../../core/api.dart';
import '../../core/colors.dart';
import '../../core/models.dart';
import '../../l10n/strings.dart';
import '../../state/providers.dart';
import '../../ui/widgets.dart';

class InviteScreen extends ConsumerWidget {
  const InviteScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(trProvider);
    final active = ref.watch(activeSocietyProvider);
    final sid = active.societyId;
    if (sid == null) return const Scaffold(body: LoadingView());
    final q = ref.watch(inviteProvider(sid));
    return AppScaffold(
      title: t('invite.title'),
      body: AsyncBody<Invite>(
        value: q,
        onRetry: () => ref.invalidate(inviteProvider(sid)),
        builder: (inv) => ListView(padding: kPad, children: [
          AppCard(
            padding: const EdgeInsets.all(24),
            child: Column(children: [
              Text(active.society?.name ?? '', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
              kGap,
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.border)),
                child: QrImageView(data: inv.deepLink, size: 200),
              ),
              kGap,
              Text(t('invite.scanHint'), textAlign: TextAlign.center, style: const TextStyle(color: AppColors.muted, fontSize: 12)),
              const SizedBox(height: 8),
              Text(t('invite.code'), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
              SelectableText(inv.code, style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w800, letterSpacing: 4)),
            ]),
          ),
          kGap,
          AppButton(t('invite.share'), icon: Icons.share, onPressed: () => SharePlus.instance.share(ShareParams(text: inv.shareText))),
          kGapS,
          AppButton(t('common.copy'), icon: Icons.copy, variant: 'secondary', onPressed: () async {
            await Clipboard.setData(ClipboardData(text: inv.code));
            if (context.mounted) toast(context, t('invite.copied'));
          }),
          AppButton(t('invite.rotate'), variant: 'ghost', onPressed: () async {
            if (!await confirmDialog(context, t, t('invite.rotate'), message: t('invite.rotateConfirm'), destructive: true)) return;
            try {
              await ref.read(apiProvider).post('/societies/$sid/invite/rotate');
              ref.read(dataVersionProvider.notifier).bump();
            } catch (e) {
              if (context.mounted) toast(context, errorText(t, e), tone: Tone.danger);
            }
          }),
        ]),
      ),
    );
  }
}
