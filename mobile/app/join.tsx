import React, { useEffect, useState } from 'react';
import { Modal, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { post } from '@/api/client';
import type { Membership, SocietyBrief } from '@/api/types';
import { Button, Card, Input, Row, Screen, T, errorMessage, toast, Ionicons, Banner } from '@/components/ui';
import { useAuth } from '@/store/auth';
import { colors, space } from '@/theme';
import { parseInviteCode } from '@/utils/deepLink';

export default function Join() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const params = useLocalSearchParams<{ code?: string }>();
  const setActive = useAuth((s) => s.setActiveSociety);
  const [code, setCode] = useState(params.code ? params.code.toUpperCase() : '');
  const [society, setSociety] = useState<SocietyBrief | null>(null);
  const [wing, setWing] = useState('');
  const [flat, setFlat] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [permission, requestPermission] = useCameraPermissions();

  const lookup = async (value = code) => {
    const parsed = parseInviteCode(value);
    if (!parsed) return setError(t('join.invalidCode'));
    setLoading(true);
    setError(null);
    try {
      setCode(parsed);
      setSociety(await post<SocietyBrief>('/societies/lookup', { invite_code: parsed }));
    } catch (e) {
      setSociety(null);
      setError(errorMessage(e, t));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (params.code) void lookup(params.code); }, []); // deep link: societypass://join?code=XXXX

  const request = async () => {
    setLoading(true);
    setError(null);
    try {
      const m = await post<Membership>('/societies/join', { invite_code: code, wing: wing.trim() || null, flat_no: flat.trim() || null });
      await qc.invalidateQueries({ queryKey: ['me'] });
      if (m.status === 'active') {
        await setActive(m.society.id);
        toast(t('join.autoApproved', { name: m.society.name }), 'success');
        router.replace('/');
      } else {
        toast(t('join.sent'), 'success');
        router.replace('/onboarding');
      }
    } catch (e) {
      setError(errorMessage(e, t));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Screen>
      {!society ? (
        <>
          <Input label={t('join.codeLabel')} value={code} onChangeText={(v) => { setCode(v.toUpperCase()); setError(null); }}
            placeholder={t('join.codePlaceholder')} autoCapitalize="characters" autoCorrect={false} error={error} maxLength={40} />
          <Button title={t('join.find')} onPress={() => lookup()} loading={loading} />
          <Button title={t('join.scanQr')} variant="secondary" icon="qr-code-outline"
            onPress={async () => { if (!permission?.granted) await requestPermission(); setScanning(true); }} />
        </>
      ) : (
        <>
          <Card>
            <Row gap={space.md}>
              <Ionicons name="business" size={28} color={colors.primary} />
              <View style={{ flex: 1 }}>
                <T variant="caption" color={colors.muted}>{t('join.joining')}</T>
                <T variant="heading">{society.name}</T>
                <T variant="caption" color={colors.muted}>{society.city}</T>
              </View>
            </Row>
          </Card>
          <Row gap={space.md}>
            <View style={{ flex: 1 }}><Input label={t('join.wing')} value={wing} onChangeText={setWing} placeholder={t('join.wingPlaceholder')} autoCapitalize="characters" maxLength={20} /></View>
            <View style={{ flex: 1 }}><Input label={t('join.flat')} value={flat} onChangeText={setFlat} placeholder={t('join.flatPlaceholder')} maxLength={20} /></View>
          </Row>
          {error ? <Banner tone="danger" text={error} /> : null}
          <Button title={t('join.request')} onPress={request} loading={loading} />
          <Button title={t('common.back')} variant="ghost" onPress={() => setSociety(null)} />
        </>
      )}

      <Modal visible={scanning} animationType="slide" onRequestClose={() => setScanning(false)}>
        <View style={{ flex: 1, backgroundColor: '#000' }}>
          {permission?.granted ? (
            <CameraView style={{ flex: 1 }} barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
              onBarcodeScanned={({ data }) => { const c = parseInviteCode(data); if (c) { setScanning(false); void lookup(c); } }} />
          ) : (
            <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.xl }}>
              <T color="#fff" style={{ textAlign: 'center' }}>{t('scan.permission')}</T>
            </View>
          )}
          <View style={{ position: 'absolute', bottom: 48, left: 24, right: 24, gap: 12 }}>
            <T color="#fff" style={{ textAlign: 'center' }}>{t('join.scanHelp')}</T>
            <Button title={t('common.close')} variant="secondary" onPress={() => setScanning(false)} />
          </View>
        </View>
      </Modal>
    </Screen>
  );
}
