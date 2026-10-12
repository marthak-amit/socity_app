import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/api.dart';
import '../../core/colors.dart';
import '../../core/models.dart';
import '../../core/utils.dart';
import '../../l10n/strings.dart';
import '../../state/providers.dart';
import '../../ui/widgets.dart';

class _TierDraft {
  _TierDraft({this.id, String name = '', String price = '', String capacity = '100', String perUser = '4', this.allowGuests = true, this.validDays = 'all', List<String>? dayDates, this.description})
      : name = TextEditingController(text: name),
        price = TextEditingController(text: price),
        capacity = TextEditingController(text: capacity),
        perUser = TextEditingController(text: perUser),
        dayDates = dayDates ?? [];
  final String? id, description;
  final TextEditingController name, price, capacity, perUser;
  bool allowGuests;
  String validDays;
  final List<String> dayDates;
}

List<String> _daysBetween(DateTime s, DateTime e) {
  final out = <String>[];
  var d = DateTime(s.year, s.month, s.day);
  final last = DateTime(e.year, e.month, e.day);
  while (!d.isAfter(last) && out.length < 31) {
    out.add(toDayString(d));
    d = d.add(const Duration(days: 1));
    d = DateTime(d.year, d.month, d.day);
  }
  return out;
}

/// Create (no id) or edit (id) an event: details, banner, paid/free, tiers (price/capacity/limit/guests/valid days).
class EventFormScreen extends ConsumerStatefulWidget {
  const EventFormScreen({super.key, this.id});
  final String? id;
  @override
  ConsumerState<EventFormScreen> createState() => _EventFormScreenState();
}

class _EventFormScreenState extends ConsumerState<EventFormScreen> {
  final _title = TextEditingController(), _desc = TextEditingController(), _venue = TextEditingController();
  DateTime? _starts, _ends, _deadline;
  bool _isPaid = true, _loaded = false, _busy = false, _lockPaid = false;
  Uint8List? _banner;
  String? _bannerMime, _bannerUrl, _error;
  final List<_TierDraft> _tiers = [_TierDraft()];
  final List<String> _removed = [];
  List<String> _existingDays = [];

  bool get _editing => widget.id != null;

  void _load(EventT ev) {
    if (_loaded) return;
    _loaded = true;
    _title.text = ev.title;
    _desc.text = ev.description ?? '';
    _venue.text = ev.venue ?? '';
    _starts = ev.startsAt;
    _ends = ev.endsAt;
    _deadline = ev.bookingDeadline;
    _isPaid = ev.isPaid;
    _bannerUrl = ev.bannerUrl;
    _existingDays = ev.days.map((d) => d.date).toList();
    _lockPaid = ev.tiers.any((x) => x.sold + x.pending > 0);
    _tiers
      ..clear()
      ..addAll(ev.tiers.map((x) => _TierDraft(
            id: x.id, name: x.name, price: '${x.price}', capacity: '${x.capacity}', perUser: '${x.perUserLimit}', allowGuests: x.allowGuests,
            validDays: x.validDays, dayDates: x.dayIds.map(ev.dayDate).where((d) => d.isNotEmpty).toList(), description: x.description)));
  }

  Future<DateTime?> _pick(DateTime? initial) async {
    final base = initial ?? DateTime.now().add(const Duration(days: 1));
    final d = await showDatePicker(context: context, initialDate: base, firstDate: DateTime.now().subtract(const Duration(days: 365)), lastDate: DateTime.now().add(const Duration(days: 730)));
    if (d == null || !mounted) return null;
    final tm = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(base));
    if (tm == null) return null;
    return DateTime(d.year, d.month, d.day, tm.hour, tm.minute);
  }

  Future<void> _pickBanner() async {
    final f = await ImagePicker().pickImage(source: ImageSource.gallery, imageQuality: 85);
    if (f == null) return;
    final b = await f.readAsBytes();
    setState(() {
      _banner = b;
      _bannerMime = f.mimeType;
    });
  }

  Map<String, dynamic> _tierBody(_TierDraft x) => {
        'name': x.name.text.trim(),
        'description': x.description,
        'price': _isPaid ? (int.tryParse(x.price.text) ?? 0) : 0,
        'capacity': int.parse(x.capacity.text),
        'per_user_limit': int.tryParse(x.perUser.text) ?? 1,
        'allow_guests': x.allowGuests,
        'valid_days': x.validDays,
        'day_dates': x.validDays == 'specific' ? x.dayDates : <String>[],
      };

  Future<void> _save(String sid) async {
    final t = ref.read(trProvider);
    if (_title.text.trim().length < 2) return setState(() => _error = t('eventForm.needTitle'));
    if (_starts == null || _ends == null || _ends!.isBefore(_starts!)) return setState(() => _error = t('eventForm.badDates'));
    if (_tiers.isEmpty) return setState(() => _error = t('eventForm.needTier'));
    for (final x in _tiers) {
      if (x.name.text.trim().isEmpty || int.tryParse(x.capacity.text) == null || (x.validDays == 'specific' && x.dayDates.isEmpty)) return setState(() => _error = t('eventForm.tierInvalid'));
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final api = ref.read(apiProvider);
    try {
      final bannerId = _banner == null ? null : await api.uploadImage(societyId: sid, purpose: 'banner', bytes: _banner!, mime: _bannerMime);
      String? eventId = widget.id;
      final common = {
        'title': _title.text.trim(),
        'description': _desc.text.trim().isEmpty ? null : _desc.text.trim(),
        'venue': _venue.text.trim().isEmpty ? null : _venue.text.trim(),
        'starts_at': _starts!.toUtc().toIso8601String(),
        'ends_at': _ends!.toUtc().toIso8601String(),
        'banner_upload_id': bannerId,
      };
      if (!_editing) {
        final created = await api.post('/societies/$sid/events', {
          ...common,
          'booking_deadline': _deadline?.toUtc().toIso8601String(),
          'is_paid': _isPaid,
          'tiers': _tiers.map(_tierBody).toList(),
        });
        eventId = created['id'] as String;
      } else {
        await api.patch('/societies/$sid/events/${widget.id}', {
          ...common,
          'booking_deadline': _deadline?.toUtc().toIso8601String(),
          'clear_booking_deadline': _deadline == null,
        });
        for (final rid in _removed) {
          await api.delete('/societies/$sid/events/${widget.id}/tiers/$rid');
        }
        for (final x in _tiers) {
          if (x.id != null) {
            await api.patch('/societies/$sid/events/${widget.id}/tiers/${x.id}', _tierBody(x));
          } else {
            await api.post('/societies/$sid/events/${widget.id}/tiers', _tierBody(x));
          }
        }
      }
      ref.read(dataVersionProvider.notifier).bump();
      if (!mounted) return;
      toast(context, t('eventForm.saved'), tone: Tone.success);
      if (_editing) {
        context.pop();
      } else {
        context.pushReplacement('/manage/event/$eventId');
      }
    } catch (e) {
      if (mounted) setState(() => _error = e is ApiError && e.code == 'validation_error' ? t('eventForm.tierInvalid') : errorText(t, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    final sid = ref.watch(activeSocietyProvider).societyId;
    if (sid == null) return const Scaffold(body: LoadingView());
    if (_editing && !_loaded) {
      final q = ref.watch(eventProvider((sid: sid, id: widget.id!)));
      return q.when(
        loading: () => const Scaffold(body: LoadingView()),
        error: (e, _) => Scaffold(appBar: AppBar(), body: ErrorView(e, onRetry: () => ref.invalidate(eventProvider((sid: sid, id: widget.id!))))),
        data: (ev) {
          _load(ev);
          return _form(t, sid);
        },
      );
    }
    return _form(t, sid);
  }

  Widget _form(Tr t, String sid) {
    final dayOptions = _editing ? _existingDays : (_starts != null && _ends != null ? _daysBetween(_starts!, _ends!) : <String>[]);
    Widget dateField(String label, DateTime? v, ValueChanged<DateTime?> set, {bool clearable = false, String? placeholder}) => AppField(
          label: label,
          hint: placeholder,
          readOnly: true,
          controller: TextEditingController(text: v == null ? '' : formatDateTime(v)),
          onTap: () async {
            final d = await _pick(v);
            if (d != null) setState(() => set(d));
          },
          suffix: clearable && v != null ? IconButton(icon: const Icon(Icons.cancel, size: 20), onPressed: () => setState(() => set(null))) : const Icon(Icons.calendar_today_outlined, size: 20),
        );

    return AppScaffold(
      title: _editing ? t('eventForm.editTitle') : t('eventForm.createTitle'),
      body: ListView(padding: kPad, children: [
        AppField(controller: _title, label: t('eventForm.title'), maxLength: 160, textCapitalization: TextCapitalization.words),
        kGap,
        AppField(controller: _desc, label: t('eventForm.description'), maxLines: 4, maxLength: 5000),
        kGap,
        AppField(controller: _venue, label: t('eventForm.venue'), maxLength: 200),
        kGap,
        dateField(t('eventForm.starts'), _starts, (d) {
          _starts = d;
          if (d != null && (_ends == null || _ends!.isBefore(d))) _ends = d.add(const Duration(hours: 3));
        }),
        kGap,
        dateField(t('eventForm.ends'), _ends, (d) => _ends = d),
        kGap,
        dateField(t('eventForm.deadline'), _deadline, (d) => _deadline = d, clearable: true, placeholder: t('eventForm.noDeadline')),
        if (dayOptions.length > 1) ...[kGap, InfoBanner('${dayOptions.length} ${t('event.days')} — ${t('eventForm.daysHelp')}', tone: Tone.info, icon: Icons.calendar_month)],
        kGap,
        Text(t('eventForm.banner'), style: const TextStyle(color: AppColors.muted, fontSize: 13)),
        kGapS,
        GestureDetector(
          onTap: _pickBanner,
          child: Container(
            height: 150,
            clipBehavior: Clip.antiAlias,
            decoration: BoxDecoration(color: AppColors.primarySoft, borderRadius: BorderRadius.circular(16)),
            child: _banner != null
                ? Image.memory(_banner!, fit: BoxFit.cover, width: double.infinity)
                : _bannerUrl != null
                    ? Image.network(_bannerUrl!, fit: BoxFit.cover, width: double.infinity)
                    : Column(mainAxisAlignment: MainAxisAlignment.center, children: [const Icon(Icons.image_outlined, size: 32, color: AppColors.primary), Text(t('eventForm.pickBanner'), style: const TextStyle(color: AppColors.primary))]),
          ),
        ),
        kGap,
        AppCard(
          child: Row(children: [
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(t('eventForm.paid'), style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
              Text(t('eventForm.paidHelp'), style: const TextStyle(color: AppColors.muted, fontSize: 12)),
            ])),
            Switch(value: _isPaid, onChanged: _lockPaid || _editing ? null : (v) => setState(() => _isPaid = v)),
          ]),
        ),
        SectionTitle(t('eventForm.tiers')),
        kGapS,
        for (var i = 0; i < _tiers.length; i++) ...[_tierCard(i, t, dayOptions), kGapS],
        AppButton(t('eventForm.addTier'), icon: Icons.add, variant: 'secondary', onPressed: () => setState(() => _tiers.add(_TierDraft()))),
        if (_error != null) ...[kGap, InfoBanner(_error!, tone: Tone.danger)],
        kGap,
        AppButton(_editing ? t('eventForm.saveChanges') : t('eventForm.saveDraft'), onPressed: () => _save(sid), loading: _busy),
        const SizedBox(height: 24),
      ]),
    );
  }

  Widget _tierCard(int i, Tr t, List<String> dayOptions) {
    final x = _tiers[i];
    return AppCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text('#${i + 1}', style: const TextStyle(color: AppColors.muted))),
          if (_tiers.length > 1)
            IconButton(
              icon: const Icon(Icons.delete_outline, color: AppColors.danger),
              onPressed: () => setState(() {
                if (x.id != null) _removed.add(x.id!);
                _tiers.removeAt(i);
              }),
            ),
        ]),
        AppField(controller: x.name, label: t('eventForm.tierName'), maxLength: 80),
        kGapS,
        Row(children: [
          if (_isPaid) ...[Expanded(child: AppField(controller: x.price, label: t('eventForm.price'), keyboardType: TextInputType.number, hint: '0')), const SizedBox(width: 8)],
          Expanded(child: AppField(controller: x.capacity, label: t('eventForm.capacity'), keyboardType: TextInputType.number)),
          const SizedBox(width: 8),
          Expanded(child: AppField(controller: x.perUser, label: t('eventForm.perUser'), keyboardType: TextInputType.number)),
        ]),
        Row(children: [Expanded(child: Text(t('eventForm.guests'))), Switch(value: x.allowGuests, onChanged: (v) => setState(() => x.allowGuests = v))]),
        if (dayOptions.length > 1) ...[
          Text(t('eventForm.validDays'), style: const TextStyle(color: AppColors.muted, fontSize: 13)),
          kGapS,
          Row(children: [
            TagChip(t('eventForm.allDays'), selected: x.validDays == 'all', onTap: () => setState(() {
                  x.validDays = 'all';
                  x.dayDates.clear();
                })),
            const SizedBox(width: 8),
            TagChip(t('eventForm.specificDays'), selected: x.validDays == 'specific', onTap: () => setState(() => x.validDays = 'specific')),
          ]),
          if (x.validDays == 'specific') ...[
            kGapS,
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final d in dayOptions) TagChip(formatDay(d), selected: x.dayDates.contains(d), onTap: () => setState(() => x.dayDates.contains(d) ? x.dayDates.remove(d) : x.dayDates.add(d))),
            ]),
          ],
        ],
      ]),
    );
  }
}
