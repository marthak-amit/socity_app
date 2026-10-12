import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api.dart';
import '../core/models.dart';
import '../core/utils.dart';
import '../l10n/strings.dart';
import '../state/providers.dart';
import '../ui/gallery_widgets.dart';
import '../ui/paged.dart';
import '../ui/widgets.dart';

class GalleryTab extends ConsumerStatefulWidget {
  const GalleryTab({super.key});
  @override
  ConsumerState<GalleryTab> createState() => _GalleryTabState();
}

class _GalleryTabState extends ConsumerState<GalleryTab> {
  String? _eventId;
  String _scope = 'all';

  Future<void> _delete(GalleryItem g) async {
    final t = ref.read(trProvider);
    final sid = ref.read(activeSocietyProvider).societyId!;
    if (!await confirmDialog(context, t, t('gallery.delete'), message: t('gallery.deleteConfirm'), confirmText: t('common.delete'), destructive: true)) return;
    try {
      await ref.read(apiProvider).delete('/societies/$sid/gallery/${g.id}');
      ref.read(dataVersionProvider.notifier).bump();
    } catch (e) {
      if (mounted) toast(context, errorText(t, e), tone: Tone.danger);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    final active = ref.watch(activeSocietyProvider);
    final sid = active.societyId;
    if (sid == null) return const LoadingView();
    final events = ref.watch(_pastEventsProvider(sid)).value ?? const <EventT>[];
    final admin = isAdminRole(active.role);
    return PagedListView<GalleryItem>(
      key: ValueKey('gallery-$sid-$_eventId-$_scope'),
      path: '/societies/$sid/gallery',
      query: {if (_eventId != null) 'event_id': _eventId, if (_scope == 'mine') 'mine': true},
      parse: GalleryItem.fromJson,
      grid: true,
      pageSize: 30,
      itemBuilder: (_, g, all) => PhotoTile(item: g, all: all, onDelete: _delete, canDelete: g.mine || admin),
      empty: EmptyState(icon: Icons.photo_library_outlined, title: t('gallery.empty'), subtitle: t('gallery.emptySub')),
      header: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SegmentedTabs<String>(value: _scope, onChanged: (v) => setState(() => _scope = v), options: [('all', t('gallery.all'), null), ('mine', t('gallery.mine'), null)]),
        kGapS,
        PhotoUploadButton(societyId: sid, eventId: _eventId, label: t('gallery.upload')),
        kGapS,
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(children: [
            TagChip(t('gallery.allEvents'), selected: _eventId == null, onTap: () => setState(() => _eventId = null)),
            for (final e in events) Padding(padding: const EdgeInsets.only(left: 8), child: TagChip(e.title, selected: _eventId == e.id, onTap: () => setState(() => _eventId = e.id))),
          ]),
        ),
      ]),
    );
  }
}

final _pastEventsProvider = FutureProvider.family<List<EventT>, String>((ref, sid) async {
  ref.watch(dataVersionProvider);
  final p = await ref.watch(apiProvider).page('/societies/$sid/events', EventT.fromJson, query: {'when': 'past'}, limit: 50);
  return p.items;
});
