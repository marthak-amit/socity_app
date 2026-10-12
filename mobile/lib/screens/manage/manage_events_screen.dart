import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/models.dart';
import '../../l10n/strings.dart';
import '../../state/providers.dart';
import '../../ui/paged.dart';
import '../../ui/widgets.dart';
import '../events_tab.dart';

class ManageEventsScreen extends ConsumerStatefulWidget {
  const ManageEventsScreen({super.key});
  @override
  ConsumerState<ManageEventsScreen> createState() => _ManageEventsScreenState();
}

class _ManageEventsScreenState extends ConsumerState<ManageEventsScreen> {
  String _filter = 'all';
  static const _filters = ['all', 'draft', 'published', 'closed', 'cancelled'];

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    final sid = ref.watch(activeSocietyProvider).societyId;
    if (sid == null) return const Scaffold(body: LoadingView());
    return AppScaffold(
      title: t('manage.events'),
      body: PagedListView<EventT>(
        key: ValueKey('mevents-$_filter'),
        path: '/societies/$sid/events',
        query: {'when': 'all', if (_filter != 'all') 'status': _filter},
        parse: EventT.fromJson,
        itemBuilder: (_, e, _) => EventCard(event: e, onTap: () => context.push('/manage/event/${e.id}')),
        empty: EmptyState(icon: Icons.calendar_today_outlined, title: t('home.emptyUpcoming')),
        header: Column(children: [
          AppButton(t('home.createEvent'), icon: Icons.add, onPressed: () => context.push('/manage/event-form')),
          kGapS,
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(children: [
              for (final f in _filters) Padding(padding: const EdgeInsets.only(right: 8), child: TagChip(f == 'all' ? t('common.all') : t('eventAdmin.statusLabel.$f'), selected: _filter == f, onTap: () => setState(() => _filter = f))),
            ]),
          ),
        ]),
      ),
    );
  }
}
