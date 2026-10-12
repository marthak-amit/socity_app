import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api.dart';
import '../core/colors.dart';
import '../l10n/strings.dart';

enum Tone { neutral, success, danger, warning, info, primary }

(Color bg, Color fg) toneColors(Tone t) => switch (t) {
      Tone.neutral => (const Color(0xFFF3F4F6), AppColors.muted),
      Tone.success => (AppColors.successSoft, AppColors.success),
      Tone.danger => (AppColors.dangerSoft, AppColors.danger),
      Tone.warning => (AppColors.warningSoft, AppColors.warning),
      Tone.info => (AppColors.infoSoft, AppColors.info),
      Tone.primary => (AppColors.primarySoft, AppColors.primary),
    };

const kGap = SizedBox(height: 12);
const kGapS = SizedBox(height: 8);
const kPad = EdgeInsets.all(16);

String errorText(Tr t, Object e) {
  if (e is ApiError) {
    final key = 'errors.${e.code}';
    return t.has(key) ? t(key) : e.message;
  }
  return t('common.error');
}

// ------------------------------------------------------------------ feedback
void toast(BuildContext context, String msg, {Tone tone = Tone.neutral}) {
  final bg = tone == Tone.danger ? AppColors.danger : tone == Tone.success ? AppColors.success : const Color(0xFF111827);
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(msg), backgroundColor: bg, behavior: SnackBarBehavior.floating, duration: const Duration(seconds: 3)));
}

Future<bool> confirmDialog(BuildContext context, Tr t, String title, {String? message, String? confirmText, bool destructive = false}) async {
  final r = await showDialog<bool>(
    context: context,
    builder: (_) => AlertDialog(
      title: Text(title),
      content: message == null ? null : Text(message),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, false), child: Text(t('common.cancel'))),
        TextButton(
          onPressed: () => Navigator.pop(context, true),
          child: Text(confirmText ?? t('common.confirm'), style: TextStyle(color: destructive ? AppColors.danger : AppColors.primary)),
        ),
      ],
    ),
  );
  return r ?? false;
}

// ------------------------------------------------------------------ basics
class AppButton extends StatelessWidget {
  const AppButton(this.label, {super.key, this.onPressed, this.icon, this.variant = 'primary', this.loading = false, this.small = false, this.expand = true});
  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final String variant; // primary | secondary | danger | ghost | success
  final bool loading, small, expand;

  @override
  Widget build(BuildContext context) {
    final (bg, fg) = switch (variant) {
      'secondary' => (AppColors.primarySoft, AppColors.primary),
      'danger' => (AppColors.danger, Colors.white),
      'ghost' => (Colors.transparent, AppColors.primary),
      'success' => (AppColors.success, Colors.white),
      _ => (AppColors.primary, Colors.white),
    };
    final enabled = onPressed != null && !loading;
    final child = loading
        ? SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: fg))
        : Row(mainAxisSize: MainAxisSize.min, mainAxisAlignment: MainAxisAlignment.center, children: [
            if (icon != null) ...[Icon(icon, size: small ? 16 : 18), const SizedBox(width: 6)],
            Flexible(child: Text(label, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600))),
          ]);
    final btn = FilledButton(
      onPressed: enabled ? onPressed : null,
      style: FilledButton.styleFrom(
        backgroundColor: bg,
        foregroundColor: fg,
        disabledBackgroundColor: bg.withValues(alpha: 0.5),
        disabledForegroundColor: fg.withValues(alpha: 0.7),
        minimumSize: Size(0, small ? 36 : 48),
        padding: EdgeInsets.symmetric(horizontal: small ? 12 : 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(small ? 8 : 12)),
        elevation: 0,
      ),
      child: child,
    );
    return expand ? SizedBox(width: double.infinity, child: btn) : btn;
  }
}

class AppCard extends StatelessWidget {
  const AppCard({super.key, required this.child, this.onTap, this.onLongPress, this.selected = false, this.padding = const EdgeInsets.all(16), this.borderColor, this.color});
  final Widget child;
  final VoidCallback? onTap, onLongPress;
  final bool selected;
  final EdgeInsets padding;
  final Color? borderColor, color;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      clipBehavior: Clip.antiAlias,
      elevation: 0,
      color: color ?? AppColors.card,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: selected ? AppColors.primary : (borderColor ?? AppColors.border), width: selected ? 2 : 1),
      ),
      child: InkWell(onTap: onTap, onLongPress: onLongPress, child: Padding(padding: padding, child: child)),
    );
  }
}

class AppBadge extends StatelessWidget {
  const AppBadge(this.text, {super.key, this.tone = Tone.neutral, this.icon});
  final String text;
  final Tone tone;
  final IconData? icon;
  @override
  Widget build(BuildContext context) {
    final (bg, fg) = toneColors(tone);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(99)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        if (icon != null) ...[Icon(icon, size: 11, color: fg), const SizedBox(width: 3)],
        Flexible(child: Text(text, style: TextStyle(color: fg, fontSize: 12, fontWeight: FontWeight.w600))),
      ]),
    );
  }
}

class InfoBanner extends StatelessWidget {
  const InfoBanner(this.text, {super.key, this.tone = Tone.warning, this.icon = Icons.error_outline});
  final String text;
  final Tone tone;
  final IconData icon;
  @override
  Widget build(BuildContext context) {
    final (bg, fg) = toneColors(tone);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(12)),
      child: Row(children: [
        Icon(icon, size: 18, color: fg),
        const SizedBox(width: 8),
        Expanded(child: Text(text, style: TextStyle(color: fg, fontSize: 13))),
      ]),
    );
  }
}

class LoadingView extends StatelessWidget {
  const LoadingView({super.key});
  @override
  Widget build(BuildContext context) => const Center(child: Padding(padding: EdgeInsets.all(32), child: CircularProgressIndicator()));
}

class EmptyState extends StatelessWidget {
  const EmptyState({super.key, this.icon = Icons.inbox_outlined, required this.title, this.subtitle, this.action});
  final IconData icon;
  final String title;
  final String? subtitle;
  final Widget? action;
  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            CircleAvatar(radius: 32, backgroundColor: AppColors.primarySoft, child: Icon(icon, size: 30, color: AppColors.primary)),
            const SizedBox(height: 12),
            Text(title, textAlign: TextAlign.center, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
            if (subtitle != null) Padding(padding: const EdgeInsets.only(top: 4), child: Text(subtitle!, textAlign: TextAlign.center, style: const TextStyle(color: AppColors.muted))),
            if (action != null) Padding(padding: const EdgeInsets.only(top: 16), child: action),
          ]),
        ),
      );
}

class ErrorView extends ConsumerWidget {
  const ErrorView(this.error, {super.key, this.onRetry});
  final Object error;
  final VoidCallback? onRetry;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final t = ref.watch(trProvider);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const CircleAvatar(radius: 32, backgroundColor: AppColors.dangerSoft, child: Icon(Icons.cloud_off, size: 30, color: AppColors.danger)),
          const SizedBox(height: 12),
          Text(errorText(t, error), textAlign: TextAlign.center, style: const TextStyle(color: AppColors.muted)),
          if (onRetry != null) Padding(padding: const EdgeInsets.only(top: 16), child: AppButton(t('common.retry'), variant: 'secondary', expand: false, onPressed: onRetry)),
        ]),
      ),
    );
  }
}

/// Renders an AsyncValue with consistent loading / error (with retry) handling.
class AsyncBody<T> extends ConsumerWidget {
  const AsyncBody({super.key, required this.value, required this.builder, this.onRetry});
  final AsyncValue<T> value;
  final Widget Function(T data) builder;
  final VoidCallback? onRetry;
  @override
  Widget build(BuildContext context, WidgetRef ref) => value.when(
        data: builder,
        loading: () => const LoadingView(),
        error: (e, _) => ErrorView(e, onRetry: onRetry),
      );
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key, this.trailing});
  final String text;
  final Widget? trailing;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 8),
        child: Row(children: [
          Expanded(child: Text(text, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700))),
          ?trailing,
        ]),
      );
}

class AppField extends StatelessWidget {
  const AppField({
    super.key, this.controller, this.label, this.hint, this.helper, this.error, this.keyboardType, this.onChanged, this.maxLines = 1,
    this.maxLength, this.autofocus = false, this.obscure = false, this.textAlign = TextAlign.start, this.textCapitalization = TextCapitalization.none,
    this.onSubmitted, this.style, this.prefix, this.readOnly = false, this.onTap, this.suffix,
  });
  final TextEditingController? controller;
  final String? label, hint, helper, error;
  final TextInputType? keyboardType;
  final ValueChanged<String>? onChanged, onSubmitted;
  final int maxLines;
  final int? maxLength;
  final bool autofocus, obscure, readOnly;
  final TextAlign textAlign;
  final TextCapitalization textCapitalization;
  final TextStyle? style;
  final String? prefix;
  final VoidCallback? onTap;
  final Widget? suffix;

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (label != null) Padding(padding: const EdgeInsets.only(bottom: 4), child: Text(label!, style: const TextStyle(color: AppColors.muted, fontSize: 13, fontWeight: FontWeight.w500))),
      TextField(
        controller: controller,
        keyboardType: keyboardType,
        onChanged: onChanged,
        onSubmitted: onSubmitted,
        maxLines: maxLines,
        minLines: maxLines > 1 ? 3 : 1,
        maxLength: maxLength,
        autofocus: autofocus,
        obscureText: obscure,
        textAlign: textAlign,
        readOnly: readOnly,
        onTap: onTap,
        textCapitalization: textCapitalization,
        style: style,
        decoration: InputDecoration(
          hintText: hint,
          counterText: '',
          prefixText: prefix,
          suffixIcon: suffix,
          errorText: error,
          helperText: helper,
          helperMaxLines: 3,
          filled: true,
          fillColor: Colors.white,
          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppColors.border)),
          enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppColors.border)),
          focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppColors.primary, width: 2)),
        ),
      ),
    ]);
  }
}

class SegmentedTabs<K> extends StatelessWidget {
  const SegmentedTabs({super.key, required this.options, required this.value, required this.onChanged});
  final List<(K key, String label, int? badge)> options;
  final K value;
  final ValueChanged<K> onChanged;
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(3),
        decoration: BoxDecoration(color: const Color(0xFFE8EAF2), borderRadius: BorderRadius.circular(12)),
        child: Row(
          children: [
            for (final o in options)
              Expanded(
                child: GestureDetector(
                  onTap: () => onChanged(o.$1),
                  behavior: HitTestBehavior.opaque,
                  child: Container(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    decoration: BoxDecoration(color: o.$1 == value ? Colors.white : null, borderRadius: BorderRadius.circular(10)),
                    child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                      Flexible(child: Text(o.$2, overflow: TextOverflow.ellipsis, style: TextStyle(fontWeight: o.$1 == value ? FontWeight.w700 : FontWeight.w500, color: o.$1 == value ? AppColors.primary : AppColors.muted))),
                      if ((o.$3 ?? 0) > 0) ...[const SizedBox(width: 6), AppBadge('${o.$3}', tone: Tone.danger)],
                    ]),
                  ),
                ),
              ),
          ],
        ),
      );
}

class TagChip extends StatelessWidget {
  const TagChip(this.label, {super.key, this.selected = false, this.onTap, this.icon});
  final String label;
  final bool selected;
  final VoidCallback? onTap;
  final IconData? icon;
  @override
  Widget build(BuildContext context) => GestureDetector(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: selected ? AppColors.primary : Colors.white,
            border: Border.all(color: selected ? AppColors.primary : AppColors.border),
            borderRadius: BorderRadius.circular(99),
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            if (icon != null) ...[Icon(icon, size: 14, color: selected ? Colors.white : AppColors.muted), const SizedBox(width: 4)],
            Text(label, style: TextStyle(fontSize: 12, fontWeight: selected ? FontWeight.w700 : FontWeight.w400, color: selected ? Colors.white : AppColors.text)),
          ]),
        ),
      );
}

class Avatar extends StatelessWidget {
  const Avatar(this.name, {super.key, this.size = 40});
  final String? name;
  final double size;
  @override
  Widget build(BuildContext context) {
    final parts = (name ?? '?').trim().split(RegExp(r'\s+')).where((s) => s.isNotEmpty).take(2).map((s) => s[0].toUpperCase()).join();
    return CircleAvatar(radius: size / 2, backgroundColor: AppColors.primarySoft, child: Text(parts.isEmpty ? '?' : parts, style: const TextStyle(color: AppColors.primary, fontWeight: FontWeight.w700)));
  }
}

/// Page scaffold used by pushed screens: back arrow, title, consistent background + refresh.
class AppScaffold extends StatelessWidget {
  const AppScaffold({super.key, required this.title, required this.body, this.actions, this.bottom, this.fab});
  final String title;
  final Widget body;
  final List<Widget>? actions;
  final Widget? bottom, fab;
  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text(title), actions: actions),
        body: body,
        bottomNavigationBar: bottom,
        floatingActionButton: fab,
      );
}

/// Scrollable column with pull-to-refresh.
class RefreshScroll extends StatelessWidget {
  const RefreshScroll({super.key, required this.children, this.onRefresh, this.padding = kPad, this.gap = 12});
  final List<Widget> children;
  final Future<void> Function()? onRefresh;
  final EdgeInsets padding;
  final double gap;
  @override
  Widget build(BuildContext context) {
    final list = ListView.separated(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: padding,
      itemCount: children.length,
      separatorBuilder: (_, _) => SizedBox(height: gap),
      itemBuilder: (_, i) => children[i],
    );
    return onRefresh == null ? list : RefreshIndicator(onRefresh: onRefresh!, child: list);
  }
}
