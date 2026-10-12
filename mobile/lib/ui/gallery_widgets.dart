import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../core/api.dart';
import '../core/colors.dart';
import '../core/models.dart';
import '../core/utils.dart';
import '../l10n/strings.dart';
import '../state/providers.dart';
import 'widgets.dart';

class PhotoTile extends ConsumerWidget {
  const PhotoTile({super.key, required this.item, required this.all, this.onDelete, this.canDelete = false});
  final GalleryItem item;
  final List<GalleryItem> all;
  final Future<void> Function(GalleryItem)? onDelete;
  final bool canDelete;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(trProvider);
    return GestureDetector(
      onTap: () => Navigator.of(context).push(MaterialPageRoute(
        fullscreenDialog: true,
        builder: (_) => PhotoViewer(items: all, initial: all.indexWhere((g) => g.id == item.id), onDelete: canDelete ? onDelete : null),
      )),
      child: Stack(fit: StackFit.expand, children: [
        CachedNetworkImage(imageUrl: item.thumbUrl, fit: BoxFit.cover, placeholder: (_, _) => Container(color: AppColors.border), errorWidget: (_, _, _) => Container(color: AppColors.border)),
        if (item.status != 'approved')
          Positioned(top: 4, left: 4, child: AppBadge(t(item.status == 'pending' ? 'gallery.pendingBadge' : 'gallery.rejectedBadge'), tone: item.status == 'pending' ? Tone.warning : Tone.danger)),
      ]),
    );
  }
}

class PhotoViewer extends ConsumerStatefulWidget {
  const PhotoViewer({super.key, required this.items, required this.initial, this.onDelete});
  final List<GalleryItem> items;
  final int initial;
  final Future<void> Function(GalleryItem)? onDelete;
  @override
  ConsumerState<PhotoViewer> createState() => _PhotoViewerState();
}

class _PhotoViewerState extends ConsumerState<PhotoViewer> {
  late final _ctrl = PageController(initialPage: widget.initial < 0 ? 0 : widget.initial);
  late int _index = widget.initial < 0 ? 0 : widget.initial;

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    final cur = widget.items[_index];
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        actions: [
          if (widget.onDelete != null)
            IconButton(
              icon: const Icon(Icons.delete_outline),
              onPressed: () async {
                final nav = Navigator.of(context);
                await widget.onDelete!(cur);
                nav.pop();
              },
            ),
        ],
      ),
      body: Stack(children: [
        PageView.builder(
          controller: _ctrl,
          itemCount: widget.items.length,
          onPageChanged: (i) => setState(() => _index = i),
          itemBuilder: (_, i) => InteractiveViewer(child: CachedNetworkImage(imageUrl: widget.items[i].url, fit: BoxFit.contain)),
        ),
        Positioned(bottom: 24, left: 16, child: Text(t('gallery.by', {'name': cur.uploaderName ?? '—'}), style: const TextStyle(color: Colors.white70))),
      ]),
    );
  }
}

/// Pick several photos → presign/PUT each → register them in the gallery (members' go to moderation).
class PhotoUploadButton extends ConsumerStatefulWidget {
  const PhotoUploadButton({super.key, required this.societyId, this.eventId, required this.label, this.small = false});
  final String societyId;
  final String? eventId;
  final String label;
  final bool small;
  @override
  ConsumerState<PhotoUploadButton> createState() => _PhotoUploadButtonState();
}

class _PhotoUploadButtonState extends ConsumerState<PhotoUploadButton> {
  bool _busy = false;

  Future<void> _pick() async {
    final t = ref.read(trProvider);
    final api = ref.read(apiProvider);
    final role = ref.read(activeSocietyProvider).role;
    final files = await ImagePicker().pickMultiImage(imageQuality: 85, limit: 10);
    if (files.isEmpty) return;
    setState(() => _busy = true);
    try {
      final ids = <String>[];
      for (final f in files) {
        ids.add(await api.uploadImage(societyId: widget.societyId, purpose: 'gallery', bytes: await f.readAsBytes(), mime: f.mimeType));
      }
      await api.post('/societies/${widget.societyId}/gallery', {'event_id': widget.eventId, 'upload_ids': ids});
      if (mounted) toast(context, isAdminRole(role) ? t('gallery.uploadedAdmin') : t('gallery.uploadedMember'), tone: Tone.success);
      ref.read(dataVersionProvider.notifier).bump();
    } catch (e) {
      if (mounted) toast(context, errorText(t, e), tone: Tone.danger);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) =>
      AppButton(widget.label, icon: Icons.cloud_upload_outlined, variant: 'secondary', small: widget.small, expand: !widget.small, loading: _busy, onPressed: _pick);
}
