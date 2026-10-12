import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'strings_en.dart';
import 'strings_gu.dart';
import 'strings_hi.dart';

const supportedLanguages = <(String, String)>[('en', 'English'), ('gu', 'ગુજરાતી'), ('hi', 'हिन्दी')];

const _tables = <String, Map<String, String>>{'en': stringsEn, 'gu': stringsGu, 'hi': stringsHi};

/// Translator: `t('order.title', {'ref': 'SP-123'})`. Falls back to English, then to the key itself.
class Tr {
  const Tr(this.lang);
  final String lang;

  String call(String key, [Map<String, Object?> args = const {}]) {
    var s = _tables[lang]?[key] ?? stringsEn[key] ?? key;
    args.forEach((k, v) => s = s.replaceAll('{{$k}}', '${v ?? ''}'));
    return s;
  }

  bool has(String key) => (_tables[lang]?.containsKey(key) ?? false) || stringsEn.containsKey(key);
}

Map<String, String> table(String lang) => _tables[lang] ?? stringsEn;

/// Current UI language ('en' | 'gu' | 'hi'). Persisted by the auth controller.
class LangController extends Notifier<String> {
  @override
  String build() => 'en';
  void set(String lang) => state = _tables.containsKey(lang) ? lang : 'en';
}

final langProvider = NotifierProvider<LangController, String>(LangController.new);
final trProvider = Provider<Tr>((ref) => Tr(ref.watch(langProvider)));
