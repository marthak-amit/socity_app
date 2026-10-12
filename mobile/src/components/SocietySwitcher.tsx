import React, { useState } from 'react';
import { Modal, Pressable, View } from 'react-native';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { Badge, Button, Card, Ionicons, Row, T } from '@/components/ui';
import { useActiveSociety } from '@/hooks/useSociety';
import { useAuth } from '@/store/auth';
import { colors, radius, space } from '@/theme';

/** Header control: shows the active society and lets the user switch (roles differ per society). */
export function SocietySwitcher() {
  const { t } = useTranslation();
  const { memberships, society, role } = useActiveSociety();
  const setActive = useAuth((s) => s.setActiveSociety);
  const [open, setOpen] = useState(false);

  return (
    <>
      <Pressable onPress={() => setOpen(true)} accessibilityRole="button" accessibilityLabel={t('switcher.title')}
        style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexShrink: 1 }}>
        <View style={{ flexShrink: 1 }}>
          <T variant="heading" numberOfLines={1}>{society?.name ?? t('common.appName')}</T>
          {role ? <T variant="caption" color={colors.muted}>{t(`roles.${role}`)}{society?.city ? ` · ${society.city}` : ''}</T> : null}
        </View>
        <Ionicons name="chevron-down" size={18} color={colors.muted} />
      </Pressable>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' }} onPress={() => setOpen(false)}>
          <Pressable style={{ backgroundColor: colors.bg, borderTopLeftRadius: radius.xl, borderTopRightRadius: radius.xl, padding: space.lg, gap: space.sm, paddingBottom: space.xxl }}>
            <T variant="title">{t('switcher.title')}</T>
            {memberships.map((m) => {
              const active = m.society.id === society?.id;
              return (
                <Card key={m.id} selected={active} onPress={m.status === 'active' ? () => { void setActive(m.society.id); setOpen(false); } : undefined}>
                  <Row style={{ justifyContent: "space-between" }}>
                    <View style={{ flex: 1 }}>
                      <T variant="heading">{m.society.name}</T>
                      <T variant="caption" color={colors.muted}>{m.society.city} · {t(`roles.${m.role}`)}</T>
                    </View>
                    {m.status === 'pending' ? <Badge text={t('switcher.pending')} tone="warning" />
                      : m.society.status === 'suspended' ? <Badge text={t('switcher.suspended')} tone="danger" />
                      : active ? <Ionicons name="checkmark-circle" size={22} color={colors.primary} /> : null}
                  </Row>
                </Card>
              );
            })}
            <Button title={t('switcher.addAnother')} variant="secondary" icon="add" onPress={() => { setOpen(false); router.push('/onboarding?add=1'); }} />
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}
