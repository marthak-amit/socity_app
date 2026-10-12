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

class OrdersScreen extends ConsumerWidget {
  const OrdersScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(trProvider);
    final sid = ref.watch(activeSocietyProvider).societyId;
    return AppScaffold(
      title: t('order.myOrders'),
      body: sid == null
          ? const LoadingView()
          : PagedListView<Order>(
              key: ValueKey('orders-$sid'),
              path: '/societies/$sid/orders/mine',
              parse: Order.fromJson,
              empty: EmptyState(icon: Icons.receipt_long_outlined, title: t('order.noOrders')),
              itemBuilder: (_, o, _) => AppCard(
                onTap: () => context.push('/order/${o.id}'),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(o.eventTitle, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                    Text('${o.refCode} · ${formatDateTime(o.createdAt)}', style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                    Text(o.items.map((i) => '${i.qty}× ${i.tierName}').join(', '), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
                  ])),
                  Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                    Text(formatInr(o.totalAmount), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 4),
                    AppBadge(o.pending ? (o.submitted ? t('order.inReview') : t('order.awaitingPayment')) : t('common.${o.status}'), tone: o.status == 'approved' ? Tone.success : (o.pending ? Tone.warning : Tone.danger)),
                  ]),
                ]),
              ),
            ),
    );
  }
}
