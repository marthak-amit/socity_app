import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:uuid/uuid.dart';

import '../core/api.dart';
import '../core/models.dart';
import '../core/utils.dart';
import '../l10n/strings.dart';
import '../state/providers.dart';
import '../ui/widgets.dart';

class _Hist {
  _Hist(this.ok, this.title, this.sub, this.at);
  final bool ok;
  final String title, sub;
  final DateTime at;
}

/// Gate scanner: green/red verdict from the server, live counters, retry-safe (client_ref) scans.
class ScanTab extends ConsumerStatefulWidget {
  const ScanTab({super.key});
  @override
  ConsumerState<ScanTab> createState() => _ScanTabState();
}

class _ScanTabState extends ConsumerState<ScanTab> {
  final _controller = MobileScannerController(formats: const [BarcodeFormat.qrCode]);
  String? _eventId;
  ScanResult? _result;
  String? _netError;
  Counters? _counters;
  final List<_Hist> _history = [];
  bool _busy = false, _torch = false;
  String? _lastToken;
  DateTime _lastAt = DateTime.fromMillisecondsSinceEpoch(0);
  Timer? _dismiss;

  @override
  void dispose() {
    _dismiss?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _reset() {
    _dismiss?.cancel();
    setState(() {
      _result = null;
      _netError = null;
      _busy = false;
    });
  }

  Future<void> _onDetect(BarcodeCapture capture, ScanEvent current, String sid) async {
    if (_busy) return;
    final token = capture.barcodes.map((b) => b.rawValue).whereType<String>().firstOrNull;
    if (token == null) return;
    final now = DateTime.now();
    if (_lastToken == token && now.difference(_lastAt).inSeconds < 3) return; // camera re-reads the same code
    _lastToken = token;
    _lastAt = now;
    _busy = true;
    final t = ref.read(trProvider);
    try {
      final r = ScanResult.fromJson(await ref.read(apiProvider).post('/societies/$sid/events/${current.eventId}/scan', {'qr_token': token, 'client_ref': const Uuid().v4()}));
      HapticFeedback.mediumImpact();
      if (!mounted) return;
      setState(() {
        _result = r;
        _counters = r.counters;
        _history.insert(0, _Hist(r.ok, r.holderName ?? t('scan.result.${r.result}'), r.tierName ?? r.message, DateTime.now()));
        if (_history.length > 15) _history.removeLast();
      });
      _dismiss = Timer(Duration(milliseconds: r.ok ? 2200 : 4500), () => mounted ? _reset() : null);
    } catch (e) {
      HapticFeedback.heavyImpact();
      _lastToken = null; // allow an immediate retry of the same code
      if (!mounted) return;
      setState(() => _netError = errorText(t, e));
      _dismiss = Timer(const Duration(milliseconds: 3500), () => mounted ? _reset() : null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    final sid = ref.watch(activeSocietyProvider).societyId;
    if (sid == null) return const LoadingView();
    final q = ref.watch(scanEventsProvider(sid));
    return AsyncBody<List<ScanEvent>>(
      value: q,
      onRetry: () => ref.invalidate(scanEventsProvider(sid)),
      builder: (list) {
        if (list.isEmpty) return EmptyState(icon: Icons.qr_code_scanner, title: t('scan.noEvents'), subtitle: t('scan.noEventsSub'));
        final current = list.where((e) => e.eventId == _eventId).firstOrNull ?? list.first;
        final counters = _counters ?? current.counters;
        final r = _result;
        return Stack(fit: StackFit.expand, children: [
          Container(color: Colors.black),
          MobileScanner(
            controller: _controller,
            onDetect: (c) => _onDetect(c, current, sid),
            errorBuilder: (context, error) => Container(
              color: Colors.black,
              padding: const EdgeInsets.all(32),
              child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                const Icon(Icons.no_photography_outlined, size: 48, color: Colors.white70),
                const SizedBox(height: 12),
                Text(t('scan.permission'), textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontSize: 16)),
                const SizedBox(height: 16),
                AppButton(t('scan.grant'), onPressed: () => _controller.start(), expand: false),
              ]),
            ),
          ),
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: Container(
              color: const Color(0xD9111827),
              padding: const EdgeInsets.all(12),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                if (list.length > 1)
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(children: [
                      for (final e in list)
                        Padding(padding: const EdgeInsets.only(right: 8), child: TagChip(e.title, selected: e.eventId == current.eventId, onTap: () => setState(() {
                              _eventId = e.eventId;
                              _counters = null;
                            }))),
                    ]),
                  ),
                Row(children: [
                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(current.title, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w700)),
                    if (current.day == null) Text(t('scan.notEventDay'), style: const TextStyle(color: Color(0xFF9CA3AF), fontSize: 12)),
                  ])),
                  IconButton(
                    tooltip: t('scan.torch'),
                    icon: Icon(_torch ? Icons.flash_on : Icons.flash_off, color: Colors.white),
                    onPressed: () async {
                      await _controller.toggleTorch();
                      setState(() => _torch = !_torch);
                    },
                  ),
                ]),
                Row(children: [
                  _counter('${counters.scannedToday}', '${t('scan.scanned')} ${t('scan.today')}', const Color(0xFF34D399)),
                  const SizedBox(width: 24),
                  _counter('${counters.expectedToday}', t('scan.expected'), Colors.white),
                  const SizedBox(width: 24),
                  _counter('${counters.sold}', t('scan.sold'), Colors.white),
                ]),
              ]),
            ),
          ),
          if (r == null && _netError == null)
            Center(child: IgnorePointer(child: Container(width: 240, height: 240, decoration: BoxDecoration(border: Border.all(color: Colors.white70, width: 3), borderRadius: BorderRadius.circular(24))))),
          if (_history.isNotEmpty && r == null && _netError == null)
            Positioned(
              bottom: 0,
              left: 0,
              right: 0,
              child: Container(
                color: const Color(0xD9111827),
                padding: const EdgeInsets.all(12),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(t('scan.recent'), style: const TextStyle(color: Color(0xFF9CA3AF), fontSize: 12)),
                  for (final h in _history.take(3))
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Row(children: [
                        Icon(h.ok ? Icons.check_circle : Icons.cancel, size: 18, color: h.ok ? const Color(0xFF34D399) : const Color(0xFFF87171)),
                        const SizedBox(width: 8),
                        Expanded(child: Text('${h.title} · ${h.sub}', overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.white))),
                        Text(formatTime(h.at), style: const TextStyle(color: Color(0xFF9CA3AF), fontSize: 12)),
                      ]),
                    ),
                ]),
              ),
            ),
          if (r != null || _netError != null)
            GestureDetector(
              onTap: _reset,
              child: Container(
                color: _netError != null ? const Color(0xFF374151) : (r!.ok ? const Color(0xFF16A34A) : const Color(0xFFDC2626)),
                padding: const EdgeInsets.all(24),
                child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                  Icon(_netError != null ? Icons.cloud_off : (r!.ok ? Icons.check_circle : Icons.cancel), size: 110, color: Colors.white),
                  const SizedBox(height: 12),
                  Text(_netError != null ? t('common.error') : (r!.ok ? t('scan.allowed') : t('scan.denied')), textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontSize: 30, fontWeight: FontWeight.w800)),
                  const SizedBox(height: 12),
                  if (_netError != null)
                    Text(_netError!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white))
                  else ...[
                    if (r!.holderName != null) Text(r.holderName!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w700)),
                    if (r.tierName != null) Text('${r.tierName}${r.holderType == 'guest' ? ' · ${t('passes.guest')}' : ''}', style: const TextStyle(color: Colors.white, fontSize: 17)),
                    const SizedBox(height: 8),
                    Text(t.has('scan.result.${r.result}') ? t('scan.result.${r.result}') : r.message, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white)),
                    if (r.result == 'already_scanned' && r.scannedAt != null)
                      Text('${t('scan.scannedAt', {'time': formatTime(r.scannedAt!)})}${r.scannedBy != null ? ' ${t('scan.by', {'name': r.scannedBy})}' : ''}', style: const TextStyle(color: Colors.white70, fontSize: 12)),
                  ],
                  const SizedBox(height: 24),
                  Text(t('scan.tapContinue'), style: const TextStyle(color: Colors.white70, fontSize: 12)),
                ]),
              ),
            ),
        ]);
      },
    );
  }

  Widget _counter(String value, String label, Color color) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(value, style: TextStyle(color: color, fontSize: 22, fontWeight: FontWeight.w800)),
        Text(label, style: const TextStyle(color: Color(0xFF9CA3AF), fontSize: 12)),
      ]);
}

