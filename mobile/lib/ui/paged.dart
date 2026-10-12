import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api.dart';
import '../core/models.dart';
import '../state/providers.dart';
import 'widgets.dart';

/// Infinite-scroll list over a paginated endpoint (`{items,total,limit,offset}`) with pull-to-refresh,
/// loading / empty / error states, and automatic refetch when [dataVersionProvider] is bumped.
class PagedListView<T> extends ConsumerStatefulWidget {
  const PagedListView({
    super.key, required this.path, required this.parse, required this.itemBuilder, required this.empty,
    this.query = const {}, this.header, this.padding = kPad, this.gap = 12, this.pageSize = 20, this.footer, this.grid = false,
  });
  final String path;
  final T Function(Json) parse;
  final Widget Function(BuildContext, T, List<T> all) itemBuilder;
  final Widget empty;
  final Map<String, dynamic> query;
  final Widget? header, footer;
  final EdgeInsets padding;
  final double gap;
  final int pageSize;
  final bool grid;

  @override
  ConsumerState<PagedListView<T>> createState() => _PagedListViewState<T>();
}

class _PagedListViewState<T> extends ConsumerState<PagedListView<T>> {
  final _scroll = ScrollController();
  final List<T> _items = [];
  int _total = 0;
  bool _loading = true, _loadingMore = false;
  Object? _error;
  int _gen = 0;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels > _scroll.position.maxScrollExtent - 300) _more();
    });
    _refresh();
  }

  @override
  void didUpdateWidget(covariant PagedListView<T> old) {
    super.didUpdateWidget(old);
    if (old.path != widget.path || '${old.query}' != '${widget.query}') {
      _items.clear();
      _loading = true;
      _refresh();
    }
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _refresh() async {
    final gen = ++_gen;
    try {
      final p = await ref.read(apiProvider).page(widget.path, widget.parse, query: widget.query, limit: widget.pageSize);
      if (!mounted || gen != _gen) return;
      setState(() {
        _items..clear()..addAll(p.items);
        _total = p.total;
        _error = null;
        _loading = false;
      });
    } catch (e) {
      if (!mounted || gen != _gen) return;
      setState(() {
        _error = e;
        _loading = false;
      });
    }
  }

  Future<void> _more() async {
    if (_loading || _loadingMore || _items.length >= _total) return;
    setState(() => _loadingMore = true);
    final gen = _gen;
    try {
      final p = await ref.read(apiProvider).page(widget.path, widget.parse, query: widget.query, limit: widget.pageSize, offset: _items.length);
      if (!mounted || gen != _gen) return;
      setState(() {
        _items.addAll(p.items);
        _total = p.total;
      });
    } catch (_) {/* keep what we have; pull-to-refresh retries */} finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(dataVersionProvider, (_, _) => _refresh());
    if (_loading) return const LoadingView();
    if (_error != null && _items.isEmpty) return ErrorView(_error!, onRetry: () => setState(() { _loading = true; _refresh(); }));
    final header = widget.header;
    if (_items.isEmpty) {
      return RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(physics: const AlwaysScrollableScrollPhysics(), padding: widget.padding, children: [
          ?header,
          SizedBox(height: 360, child: widget.empty),
        ]),
      );
    }
    final extra = (header != null ? 1 : 0);
    if (widget.grid) {
      return RefreshIndicator(
        onRefresh: _refresh,
        child: CustomScrollView(controller: _scroll, physics: const AlwaysScrollableScrollPhysics(), slivers: [
          if (header != null) SliverToBoxAdapter(child: Padding(padding: widget.padding, child: header)),
          SliverPadding(
            padding: const EdgeInsets.symmetric(horizontal: 2),
            sliver: SliverGrid.builder(
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 3, mainAxisSpacing: 3, crossAxisSpacing: 3),
              itemCount: _items.length,
              itemBuilder: (c, i) => widget.itemBuilder(c, _items[i], _items),
            ),
          ),
          SliverToBoxAdapter(child: _loadingMore ? const LoadingView() : (widget.footer ?? const SizedBox(height: 80))),
        ]),
      );
    }
    return RefreshIndicator(
      onRefresh: _refresh,
      child: ListView.separated(
        controller: _scroll,
        physics: const AlwaysScrollableScrollPhysics(),
        padding: widget.padding,
        itemCount: _items.length + extra + 1,
        separatorBuilder: (_, _) => SizedBox(height: widget.gap),
        itemBuilder: (c, i) {
          if (header != null && i == 0) return header;
          final idx = i - extra;
          if (idx == _items.length) return _loadingMore ? const LoadingView() : (widget.footer ?? const SizedBox(height: 60));
          return widget.itemBuilder(c, _items[idx], _items);
        },
      ),
    );
  }
}
