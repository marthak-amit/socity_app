import React, { useState } from 'react';
import { KeyboardAvoidingView, Platform, View } from 'react-native';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { Ionicons } from '@expo/vector-icons';
import { post } from '@/api/client';
import { Button, Input, Screen, T, errorMessage } from '@/components/ui';
import { colors, space } from '@/theme';
import { normalizeIndianPhone } from '@/utils/validation';

export default function Login() {
  const { t } = useTranslation();
  const [phone, setPhone] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    const normalized = normalizeIndianPhone(phone);
    if (!normalized) return setError(t('auth.invalidPhone'));
    setError(null);
    setLoading(true);
    try {
      const res = await post<{ dev_otp?: string | null }>('/auth/otp/request', { phone: normalized });
      router.push({ pathname: '/otp', params: { phone: normalized, dev: res.dev_otp ?? '' } });
    } catch (e) {
      setError(errorMessage(e, t));
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Screen edges={['top', 'bottom', 'left', 'right']}>
        <View style={{ alignItems: 'center', marginTop: space.xxl * 1.5, marginBottom: space.xl, gap: space.sm }}>
          <View style={{ width: 76, height: 76, borderRadius: 22, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="ticket" size={40} color="#fff" />
          </View>
          <T variant="display">{t('common.appName')}</T>
          <T color={colors.muted} style={{ textAlign: 'center' }}>{t('auth.welcome')}</T>
        </View>
        <Input
          label={t('auth.phoneLabel')} value={phone} onChangeText={(v) => { setPhone(v); setError(null); }} keyboardType="phone-pad"
          placeholder={t('auth.phonePlaceholder')} maxLength={16} error={error} autoFocus textContentType="telephoneNumber"
          onSubmitEditing={submit} returnKeyType="go"
        />
        <T variant="caption" color={colors.muted}>+91</T>
        <Button title={t('auth.sendOtp')} onPress={submit} loading={loading} />
        <T variant="caption" color={colors.faint} style={{ textAlign: 'center', marginTop: space.lg }}>{t('auth.terms')}</T>
      </Screen>
    </KeyboardAvoidingView>
  );
}
