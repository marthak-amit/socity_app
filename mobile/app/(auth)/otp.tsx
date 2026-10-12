import React, { useEffect, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { post } from '@/api/client';
import type { TokenPair } from '@/api/types';
import { Button, Input, Screen, T, errorMessage, Banner } from '@/components/ui';
import { useAuth } from '@/store/auth';
import { colors } from '@/theme';
import { isValidOtp } from '@/utils/validation';

export default function Otp() {
  const { t } = useTranslation();
  const { phone, dev } = useLocalSearchParams<{ phone: string; dev?: string }>();
  const qc = useQueryClient();
  const setSession = useAuth((s) => s.setSession);
  const [code, setCode] = useState(dev ?? '');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [seconds, setSeconds] = useState(30);

  useEffect(() => {
    if (seconds <= 0) return;
    const id = setTimeout(() => setSeconds((s) => s - 1), 1000);
    return () => clearTimeout(id);
  }, [seconds]);

  const verify = async (value = code) => {
    if (!isValidOtp(value)) return setError(t('auth.invalidOtp'));
    setLoading(true);
    setError(null);
    try {
      const res = await post<TokenPair>('/auth/otp/verify', { phone, code: value });
      qc.clear();
      await setSession(res.access_token, res.refresh_token, res.user);
      // The root layout swaps the (auth) stack for the app stack; then we pick the right first screen.
      router.replace(res.user.name ? '/' : '/profile-setup');
    } catch (e) {
      setError(errorMessage(e, t));
    } finally {
      setLoading(false);
    }
  };

  const resend = async () => {
    try {
      const res = await post<{ dev_otp?: string | null }>('/auth/otp/request', { phone });
      setSeconds(30);
      setError(null);
      if (res.dev_otp) setCode(res.dev_otp);
    } catch (e) {
      setError(errorMessage(e, t));
    }
  };

  return (
    <Screen edges={['top', 'bottom', 'left', 'right']}>
      <T variant="title" style={{ marginTop: 48 }}>{t('auth.otpTitle')}</T>
      <T color={colors.muted}>{t('auth.otpSent', { phone })}</T>
      {dev ? <Banner tone="info" icon="bug" text={t('auth.devHint', { code: dev })} /> : null}
      <Input
        label={t('auth.otpLabel')} value={code} onChangeText={(v) => { const c = v.replace(/\D/g, '').slice(0, 6); setCode(c); setError(null); if (c.length === 6) void verify(c); }}
        keyboardType="number-pad" maxLength={6} autoFocus textContentType="oneTimeCode" autoComplete="sms-otp" error={error}
        style={{ fontSize: 24, letterSpacing: 8, textAlign: 'center' }}
      />
      <Button title={t('auth.verify')} onPress={() => verify()} loading={loading} />
      <Button title={seconds > 0 ? t('auth.resendIn', { seconds }) : t('auth.resend')} variant="ghost" disabled={seconds > 0} onPress={resend} />
    </Screen>
  );
}
