import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/api.dart';
import '../core/colors.dart';
import '../core/models.dart';
import '../core/utils.dart';
import '../l10n/strings.dart';
import '../state/auth.dart';
import '../state/providers.dart';
import '../ui/widgets.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});
  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _phone = TextEditingController();
  String? _error;
  bool _loading = false;

  Future<void> _submit() async {
    final t = ref.read(trProvider);
    final phone = normalizeIndianPhone(_phone.text);
    if (phone == null) return setState(() => _error = t('auth.invalidPhone'));
    setState(() {
      _error = null;
      _loading = true;
    });
    try {
      final res = await ref.read(apiProvider).request('POST', '/auth/otp/request', body: {'phone': phone}, auth: false) as Json;
      if (mounted) context.push('/otp', extra: {'phone': phone, 'dev': res['dev_otp']});
    } catch (e) {
      if (mounted) setState(() => _error = errorText(t, e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Center(
                  child: Container(
                    width: 76,
                    height: 76,
                    decoration: BoxDecoration(color: AppColors.primary, borderRadius: BorderRadius.circular(22)),
                    child: const Icon(Icons.confirmation_number, size: 40, color: Colors.white),
                  ),
                ),
                const SizedBox(height: 12),
                Text(t('common.appName'), textAlign: TextAlign.center, style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w800)),
                Text(t('auth.welcome'), textAlign: TextAlign.center, style: const TextStyle(color: AppColors.muted)),
                const SizedBox(height: 32),
                AppField(
                  controller: _phone,
                  label: t('auth.phoneLabel'),
                  hint: t('auth.phonePlaceholder'),
                  prefix: '+91  ',
                  keyboardType: TextInputType.phone,
                  maxLength: 16,
                  autofocus: true,
                  error: _error,
                  onChanged: (_) => setState(() => _error = null),
                  onSubmitted: (_) => _submit(),
                ),
                kGap,
                AppButton(t('auth.sendOtp'), onPressed: _submit, loading: _loading),
                const SizedBox(height: 16),
                Text(t('auth.terms'), textAlign: TextAlign.center, style: const TextStyle(color: AppColors.faint, fontSize: 12)),
              ]),
            ),
          ),
        ),
      ),
    );
  }
}

class OtpScreen extends ConsumerStatefulWidget {
  const OtpScreen({super.key, required this.phone, this.devCode});
  final String phone;
  final String? devCode;
  @override
  ConsumerState<OtpScreen> createState() => _OtpScreenState();
}

class _OtpScreenState extends ConsumerState<OtpScreen> {
  late final TextEditingController _code = TextEditingController(text: widget.devCode ?? '');
  String? _error;
  bool _loading = false;
  int _seconds = 30;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (_seconds > 0 && mounted) setState(() => _seconds--);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _verify([String? value]) async {
    final t = ref.read(trProvider);
    final code = value ?? _code.text;
    if (!isValidOtp(code)) return setState(() => _error = t('auth.invalidOtp'));
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final j = await ref.read(apiProvider).request('POST', '/auth/otp/verify', body: {'phone': widget.phone, 'code': code}, auth: false) as Json;
      await ref.read(authProvider.notifier).setSession(j['access_token'], j['refresh_token'], User.fromJson(j['user']));
      ref.read(dataVersionProvider.notifier).bump();
      // Reset to a clean stack (the OTP page was pushed on top of login); the redirect then picks
      // profile setup → onboarding → tabs.
      if (mounted) context.go('/');
    } catch (e) {
      if (mounted) setState(() => _error = errorText(t, e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _resend() async {
    final t = ref.read(trProvider);
    try {
      final res = await ref.read(apiProvider).request('POST', '/auth/otp/request', body: {'phone': widget.phone}, auth: false) as Json;
      setState(() {
        _seconds = 30;
        _error = null;
        if (res['dev_otp'] != null) _code.text = res['dev_otp'];
      });
    } catch (e) {
      if (mounted) setState(() => _error = errorText(t, e));
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    return Scaffold(
      appBar: AppBar(),
      body: ListView(padding: const EdgeInsets.all(24), children: [
        Text(t('auth.otpTitle'), style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w800)),
        const SizedBox(height: 4),
        Text(t('auth.otpSent', {'phone': widget.phone}), style: const TextStyle(color: AppColors.muted)),
        if (widget.devCode != null && widget.devCode!.isNotEmpty) ...[kGap, InfoBanner(t('auth.devHint', {'code': widget.devCode}), tone: Tone.info, icon: Icons.bug_report_outlined)],
        const SizedBox(height: 20),
        AppField(
          controller: _code,
          label: t('auth.otpLabel'),
          keyboardType: TextInputType.number,
          maxLength: 6,
          autofocus: true,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 24, letterSpacing: 8),
          error: _error,
          onChanged: (v) {
            setState(() => _error = null);
            if (v.length == 6) _verify(v);
          },
        ),
        kGap,
        AppButton(t('auth.verify'), onPressed: _verify, loading: _loading),
        AppButton(_seconds > 0 ? t('auth.resendIn', {'seconds': _seconds}) : t('auth.resend'), variant: 'ghost', onPressed: _seconds > 0 ? null : _resend),
      ]),
    );
  }
}

class ProfileSetupScreen extends ConsumerStatefulWidget {
  const ProfileSetupScreen({super.key});
  @override
  ConsumerState<ProfileSetupScreen> createState() => _ProfileSetupScreenState();
}

class _ProfileSetupScreenState extends ConsumerState<ProfileSetupScreen> {
  final _name = TextEditingController();
  String? _error;
  bool _loading = false;

  Future<void> _save() async {
    final t = ref.read(trProvider);
    if (_name.text.trim().length < 2) return setState(() => _error = t('common.required'));
    setState(() => _loading = true);
    try {
      final me = Me.fromJson(await ref.read(apiProvider).patch('/me', {'name': _name.text.trim()}));
      await ref.read(authProvider.notifier).setUser(me.user);
      ref.read(dataVersionProvider.notifier).bump();
      if (mounted) context.go('/');
    } catch (e) {
      if (mounted) setState(() => _error = errorText(t, e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = ref.watch(trProvider);
    return Scaffold(
      appBar: AppBar(title: Text(t('auth.yourName'))),
      body: ListView(padding: const EdgeInsets.all(24), children: [
        Text(t('auth.nameHelp'), style: const TextStyle(color: AppColors.muted)),
        kGap,
        AppField(controller: _name, hint: t('auth.namePlaceholder'), autofocus: true, error: _error, textCapitalization: TextCapitalization.words, onSubmitted: (_) => _save()),
        kGap,
        AppButton(t('common.continue'), onPressed: _save, loading: _loading),
      ]),
    );
  }
}
