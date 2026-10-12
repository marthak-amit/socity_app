import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api.dart';
import '../../core/colors.dart';
import '../../core/models.dart';
import '../../core/utils.dart';
import '../../l10n/strings.dart';
import '../../state/providers.dart';
import '../../ui/paged.dart';
import '../../ui/widgets.dart';

class ModerationScreen extends ConsumerWidget {
  const ModerationScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(trProvider);
    final sid = ref.watch(activeSocietyProvider).societyId;
    if (sid == null) return const Scaffold(body: LoadingView());
    Future<void> act(GalleryItem g, String action) async {
      try {
        await ref.read(apiProvider).post('/societies/$sid/gallery/${g.id}/$action');
        ref.read(dataVersionProvider.notifier).bump();
      } catch (e) {
        if (context.mounted) toast(context, errorText(t, e), tone: Tone.danger);
      }
    }

    return AppScaffold(
      title: t('moderation.title'),
      body: PagedListView<GalleryItem>(
        path: '/societies/$sid/gallery',
        query: const {'status': 'pending'},
        parse: GalleryItem.fromJson,
        empty: EmptyState(icon: Icons.photo_library_outlined, title: t('moderation.empty')),
        itemBuilder: (_, g, _) => AppCard(
          padding: EdgeInsets.zero,
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            CachedNetworkImage(imageUrl: g.url, height: 260, width: double.infinity, fit: BoxFit.cover),
            Padding(
              padding: const EdgeInsets.all(12),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('${t('moderation.uploadedBy', {'name': g.uploaderName ?? '—'})} · ${formatDateTime(g.createdAt)}', style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                kGapS,
                Row(children: [
                  Expanded(child: AppButton(t('moderation.reject'), variant: 'secondary', onPressed: () => act(g, 'reject'))),
                  const SizedBox(width: 8),
                  Expanded(child: AppButton(t('moderation.approve'), variant: 'success', onPressed: () => act(g, 'approve'))),
                ]),
              ]),
            ),
          ]),
        ),
      ),
    );
  }
}
