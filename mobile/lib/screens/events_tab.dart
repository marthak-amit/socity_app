import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/colors.dart';
import '../core/models.dart';
import '../core/utils.dart';
import '../l10n/strings.dart';
import '../state/providers.dart';
import '../ui/paged.dart';
import '../ui/widgets.dart';

class EventCard extends ConsumerWidget {
  const EventCard({super.key, required this.event, this.onTap});
  final EventT event;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(trProvider);
    final price = event.minPrice;
    return AppCard(
      padding: EdgeInsets.zero,
      onTap: onTap ?? () => context.push('/event/${event.id}'),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SizedBox(
          height: 150,
          width: double.infinity,
          child: Stack(fit: StackFit.expand, children: [
            Container(color: AppColors.primarySoft, child: const Icon(Icons.auto_awesome, size: 40, color: AppColors.primary)),
            if (event.bannerUrl != null) CachedNetworkImage(imageUrl: event.bannerUrl!, fit: BoxFit.cover, errorWidget: (_, _, _) => const SizedBox()),
            Positioned(top: 10, left: 10, child: Wrap(spacing: 6, children: [
              if (event.status == 'draft') AppBadge(t('home.draft'), tone: Tone.warning),
              if (event.status == 'cancelled') AppBadge(t('home.cancelledBadge'), tone: Tone.danger),
              if (event.status == 'closed') AppBadge(t('home.closed')),
              if (event.soldOut && event.status == 'published') AppBadge(t('home.soldOut'), tone: Tone.danger),
            ])),
          ]),
        ),
        Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(event.title, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            Row(children: [
              const Icon(Icons.calendar_today, size: 14, color: AppColors.muted),
              const SizedBox(width: 6),
              Text('${formatDateRange(event.startsAt, event.endsAt)} · ${formatTime(event.startsAt)}', style: const TextStyle(color: AppColors.muted, fontSize: 12)),
            ]),
            if (event.venue != null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Row(children: [
                  const Icon(Icons.place_outlined, size: 14, color: AppColors.muted),
                  const SizedBox(width: 6),
                  Expanded(child: Text(event.venue!, overflow: TextOverflow.ellipsis, style: const TextStyle(color: AppColors.muted, fontSize: 12))),
                ]),
              ),
            if (price != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: AppBadge(price == 0 ? t('home.free') : t('home.from', {'price': formatInr(price)}), tone: Tone.primary),
              ),
          ]),
        ),
      ]),
    );
  }
}

class EventsTab extends ConsumerStatefulWidget {
  const EventsTab({super.key});
  @override
  ConsumerState<EventsTab> createState() => _EventsTabState();
}

class _EventsTabState extends ConsumerState<EventsTab> {
  String _when = 'upcoming';

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    final active = ref.watch(activeSocietyProvider);
    if (active.suspended) return EmptyState(icon: Icons.pause_circle_outline, title: t('home.suspendedTitle'), subtitle: t('home.suspendedBody'));
    final sid = active.societyId;
    if (sid == null) return EmptyState(icon: Icons.apartment, title: t('home.noSociety'));
    return PagedListView<EventT>(
      key: ValueKey('events-$sid-$_when'),
      path: '/societies/$sid/events',
      query: {'when': _when},
      parse: EventT.fromJson,
      itemBuilder: (_, e, _) => EventCard(event: e),
      empty: EmptyState(
        icon: Icons.calendar_today_outlined,
        title: _when == 'upcoming' ? t('home.emptyUpcoming') : t('home.emptyPast'),
        subtitle: _when == 'upcoming' ? t('home.emptyUpcomingSub') : null,
      ),
      header: Column(children: [
        SegmentedTabs<String>(value: _when, onChanged: (v) => setState(() => _when = v), options: [('upcoming', t('home.upcoming'), null), ('past', t('home.past'), null)]),
        if (isAdminRole(active.role)) ...[
          kGapS,
          AppButton(t('home.createEvent'), icon: Icons.add, variant: 'secondary', small: true, onPressed: () => context.push('/manage/event-form')),
        ],
      ]),
    );
  }
}
