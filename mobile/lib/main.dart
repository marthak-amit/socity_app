import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(ProviderScope(
    // Failed requests surface as error states with a manual "Try again"; no silent auto-retry storms.
    retry: (_, _) => null,
    child: const SocietyPassApp(),
  ));
}
