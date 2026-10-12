import React from 'react';
import { ColorValue, View } from 'react-native';
import { Redirect, Tabs, router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';
import { IconButton, useFont } from '@/components/ui';
import { SocietySwitcher } from '@/components/SocietySwitcher';
import { useActiveSociety } from '@/hooks/useSociety';
import { usePushRegistration } from '@/hooks/usePush';
import { colors, space } from '@/theme';
import { tabsForRole } from '@/utils/roles';

function Header() {
  const insets = useSafeAreaInsets();
  return (
    <View style={{ paddingTop: insets.top + 6, paddingBottom: 10, paddingHorizontal: space.lg, backgroundColor: colors.card, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
      <View style={{ flex: 1 }}><SocietySwitcher /></View>
      <IconButton icon="receipt-outline" label="Orders" onPress={() => router.push('/orders')} />
      <IconButton icon="settings-outline" label="Settings" onPress={() => router.push('/settings')} />
    </View>
  );
}

export default function TabsLayout() {
  const { t } = useTranslation();
  const fonts = useFont();
  const { role, societyId, isLoading } = useActiveSociety();
  usePushRegistration();
  if (!isLoading && !societyId) return <Redirect href="/onboarding" />;
  const visible = tabsForRole(role);
  const opt = (key: string, title: string, icon: React.ComponentProps<typeof Ionicons>['name'], iconActive: typeof icon) => ({
    title, href: (visible as string[]).includes(key) ? undefined : null,
    tabBarIcon: ({ focused, color, size }: { focused: boolean; color: ColorValue; size: number }) => <Ionicons name={focused ? iconActive : icon} size={size} color={color} />,
  });

  return (
    <Tabs screenOptions={{
      header: () => <Header />, tabBarActiveTintColor: colors.primary, tabBarInactiveTintColor: colors.faint,
      tabBarLabelStyle: { fontFamily: fonts.medium, fontSize: 11 }, tabBarStyle: { backgroundColor: colors.card, borderTopColor: colors.border },
    }}>
      <Tabs.Screen name="index" options={opt('index', t('tabs.home'), 'calendar-outline', 'calendar')} />
      <Tabs.Screen name="passes" options={opt('passes', t('tabs.passes'), 'ticket-outline', 'ticket')} />
      <Tabs.Screen name="gallery" options={opt('gallery', t('tabs.gallery'), 'images-outline', 'images')} />
      <Tabs.Screen name="scan" options={opt('scan', t('tabs.scan'), 'qr-code-outline', 'qr-code')} />
      <Tabs.Screen name="manage" options={opt('manage', t('tabs.manage'), 'briefcase-outline', 'briefcase')} />
    </Tabs>
  );
}
