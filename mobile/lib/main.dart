import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  // Surface uncaught errors in logs (also in release builds) instead of failing silently.
  FlutterError.onError = (d) {
    FlutterError.presentError(d);
    debugPrint('FlutterError: ${d.exceptionAsString()}\n${d.stack}');
  };
  PlatformDispatcher.instance.onError = (e, s) {
    debugPrint('Uncaught: $e\n$s');
    return true;
  };
  runApp(ProviderScope(
    // Failed requests surface as error states with a manual "Try again"; no silent auto-retry storms.
    retry: (_, _) => null,
    child: const SocietyPassApp(),
  ));
}
