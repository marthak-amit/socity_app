import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import 'core/colors.dart';
import 'core/push.dart';
import 'l10n/strings.dart';
import 'router.dart';
import 'state/auth.dart';
import 'state/providers.dart';

ThemeData buildTheme(String lang) {
  final base = ThemeData(
    useMaterial3: true,
    colorScheme: ColorScheme.fromSeed(seedColor: AppColors.primary, surface: AppColors.card),
    scaffoldBackgroundColor: AppColors.bg,
  );
  // Noto Sans covers Latin; the Gujarati / Devanagari families are used when the UI language needs them.
  TextTheme text(TextTheme t) => switch (lang) {
        'gu' => GoogleFonts.notoSansGujaratiTextTheme(t),
        'hi' => GoogleFonts.notoSansDevanagariTextTheme(t),
        _ => GoogleFonts.notoSansTextTheme(t),
      };
  return base.copyWith(
    textTheme: text(base.textTheme).apply(bodyColor: AppColors.text, displayColor: AppColors.text),
    appBarTheme: AppBarTheme(
      backgroundColor: AppColors.card,
      foregroundColor: AppColors.text,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
      titleTextStyle: text(base.textTheme).titleMedium?.copyWith(fontWeight: FontWeight.w700, fontSize: 18, color: AppColors.text),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: AppColors.card,
      indicatorColor: AppColors.primarySoft,
      labelTextStyle: WidgetStatePropertyAll(text(base.textTheme).labelSmall?.copyWith(fontWeight: FontWeight.w600)),
    ),
    dividerTheme: const DividerThemeData(color: AppColors.border, space: 24),
  );
}

class SocietyPassApp extends ConsumerStatefulWidget {
  const SocietyPassApp({super.key});
  @override
  ConsumerState<SocietyPassApp> createState() => _SocietyPassAppState();
}

class _SocietyPassAppState extends ConsumerState<SocietyPassApp> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(authProvider.notifier).hydrate());
  }

  @override
  Widget build(BuildContext context) {
    final lang = ref.watch(langProvider);
    final ready = ref.watch(authProvider.select((s) => s.ready));
    final loggedIn = ref.watch(authProvider.select((s) => s.loggedIn));
    final router = ref.watch(routerProvider);

    // Keep the stored active society valid, register for pushes after sign-in.
    ref.listen(activeSocietyProvider, (_, a) {
      final id = a.societyId;
      if (a.me != null && id != ref.read(authProvider).activeSocietyId) ref.read(authProvider.notifier).setActiveSociety(id);
    });
    ref.listen(authProvider.select((s) => s.loggedIn), (_, v) {
      if (v) ref.read(pushServiceProvider).start(router);
    });
    if (ready && loggedIn) Future.microtask(() => ref.read(pushServiceProvider).start(router));

    if (!ready) {
      return MaterialApp(theme: buildTheme(lang), debugShowCheckedModeBanner: false, home: const Scaffold(body: Center(child: CircularProgressIndicator())));
    }
    return MaterialApp.router(
      title: 'SocietyPass',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(lang),
      locale: Locale(lang),
      supportedLocales: [for (final l in supportedLanguages) Locale(l.$1)],
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
      routerConfig: router,
    );
  }
}
