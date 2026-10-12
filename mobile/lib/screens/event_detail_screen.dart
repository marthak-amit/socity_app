import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/colors.dart';
import '../core/models.dart';
import '../core/utils.dart';
import '../l10n/strings.dart';
import '../state/providers.dart';
import '../ui/gallery_widgets.dart';
import '../ui/paged.dart';
import '../ui/widgets.dart';

class EventDetailScreen extends ConsumerWidget {
  const EventDetailScreen({super.key, required this.id});
  final String id;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(trProvider);
    final active = ref.watch(activeSocietyProvider);
    final sid = active.societyId;
    if (sid == null) return const Scaffold(body: LoadingView());
    final q = ref.watch(eventProvider((sid: sid, id: id)));

    return Scaffold(
      appBar: AppBar(),
      body: AsyncBody<EventT>(
        value: q,
        onRetry: () => ref.invalidate(eventProvider((sid: sid, id: id))),
        builder: (ev) {
          String dayLabel(List<String> ids) => ev.days.where((d) => ids.contains(d.id)).map((d) => formatDay(d.date)).join(', ');
          final canBook = ev.bookingOpen && ev.tiers.any((x) => x.remaining > 0);
          return Column(children: [
            Expanded(
              child: RefreshIndicator(
                onRefresh: () async => ref.read(dataVersionProvider.notifier).bump(),
                child: ListView(physics: const AlwaysScrollableScrollPhysics(), children: [
                  SizedBox(
                    height: 200,
                    child: Stack(fit: StackFit.expand, children: [
                      Container(color: AppColors.primarySoft, child: const Icon(Icons.auto_awesome, size: 56, color: AppColors.primary)),
                      if (ev.bannerUrl != null) CachedNetworkImage(imageUrl: ev.bannerUrl!, fit: BoxFit.cover, errorWidget: (_, _, _) => const SizedBox()),
                    ]),
                  ),
                  Padding(
                    padding: kPad,
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Wrap(spacing: 6, children: [
                        if (ev.status == 'draft') AppBadge(t('home.draft'), tone: Tone.warning),
                        if (ev.status == 'cancelled') AppBadge(t('home.cancelledBadge'), tone: Tone.danger),
                        if (ev.status == 'closed') AppBadge(t('home.closed')),
                        if (ev.days.length > 1) AppBadge('${ev.days.length} ${t('event.days')}', tone: Tone.primary),
                      ]),
                      const SizedBox(height: 8),
                      Text(ev.title, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w800)),
                      kGap,
                      AppCard(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          _infoRow(Icons.schedule, t('event.when'), '${formatDateTime(ev.startsAt)}\n→ ${formatDateTime(ev.endsAt)}'),
                          if (ev.venue != null) ...[kGap, _infoRow(Icons.place_outlined, t('event.venue'), ev.venue!)],
                          if (ev.bookingDeadline != null) ...[kGap, _infoRow(Icons.hourglass_bottom, '', t('event.deadline', {'date': formatDateTime(ev.bookingDeadline!)}), color: AppColors.warning)],
                        ]),
                      ),
                      if (ev.status == 'cancelled') ...[kGap, InfoBanner(t('event.cancelled'), tone: Tone.danger)],
                      if (ev.description != null) ...[SectionTitle(t('event.about')), kGapS, Text(ev.description!)],
                      SectionTitle(t('event.passes')),
                      kGapS,
                      for (final tier in ev.tiers) ...[
                        Opacity(
                          opacity: tier.remaining == 0 ? 0.6 : 1,
                          child: AppCard(
                            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              Row(children: [
                                Expanded(child: Text(tier.name, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700))),
                                Text(priceLabel(tier.price, free: t('common.free')), style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: AppColors.primary)),
                              ]),
                              if (tier.description != null) Text(tier.description!, style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                              const SizedBox(height: 8),
                              Wrap(spacing: 6, runSpacing: 6, children: [
                                tier.remaining == 0
                                    ? AppBadge(t('event.soldOut'), tone: Tone.danger)
                                    : AppBadge(t('event.left', {'n': tier.remaining}), tone: tier.remaining <= 10 ? Tone.warning : Tone.success),
                                AppBadge(tier.validDays == 'all' ? t('event.allDays') : t('event.validOn', {'days': dayLabel(tier.dayIds)})),
                                if (tier.allowGuests) AppBadge(t('event.guestsOk'), tone: Tone.info),
                                AppBadge(t('event.maxPerUser', {'n': tier.perUserLimit})),
                              ]),
                            ]),
                          ),
                        ),
                        kGapS,
                      ],
                      if (isAdminRole(active.role)) AppButton(t('event.manage'), icon: Icons.construction, variant: 'secondary', onPressed: () => context.push('/manage/event/${ev.id}')),
                      if (ev.isOver || isAdminRole(active.role)) ...[
                        SectionTitle(t('event.photos'), trailing: PhotoUploadButton(societyId: sid, eventId: ev.id, label: t('event.addPhotos'), small: true)),
                        kGapS,
                        SizedBox(
                          height: 320,
                          child: PagedListView<GalleryItem>(
                            key: ValueKey('evgal-${ev.id}'),
                            path: '/societies/$sid/gallery',
                            query: {'event_id': ev.id},
                            parse: GalleryItem.fromJson,
                            grid: true,
                            padding: EdgeInsets.zero,
                            pageSize: 30,
                            itemBuilder: (_, g, all) => PhotoTile(item: g, all: all),
                            empty: Center(child: Text(t('event.noPhotos'), style: const TextStyle(color: AppColors.muted))),
                          ),
                        ),
                      ] else ...[
                        kGap,
                        InfoBanner(t('event.photosLocked'), tone: Tone.info, icon: Icons.photo_library_outlined),
                      ],
                    ]),
                  ),
                ]),
              ),
            ),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: const BoxDecoration(color: AppColors.card, border: Border(top: BorderSide(color: AppColors.border))),
              child: SafeArea(
                top: false,
                child: canBook
                    ? AppButton(t('event.getPasses'), icon: Icons.confirmation_number, onPressed: () => context.push('/event/${ev.id}/buy'))
                    : AppButton(
                        ev.isOver ? t('event.eventOver') : (!ev.tiers.any((x) => x.remaining > 0) && ev.bookingOpen ? t('event.soldOut') : t('event.bookingClosed')),
                        variant: 'secondary',
                      ),
              ),
            ),
          ]);
        },
      ),
    );
  }

  Widget _infoRow(IconData icon, String label, String value, {Color color = AppColors.primary}) => Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(icon, size: 20, color: color),
        const SizedBox(width: 12),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (label.isNotEmpty) Text(label, style: const TextStyle(color: AppColors.muted, fontSize: 12)),
          Text(value),
        ])),
      ]);
}
