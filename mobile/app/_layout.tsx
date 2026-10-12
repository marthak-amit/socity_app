import '@/i18n';
import React, { useEffect } from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import * as SplashScreen from 'expo-splash-screen';
import { useFonts } from 'expo-font';
import { NotoSans_400Regular, NotoSans_500Medium, NotoSans_700Bold } from '@expo-google-fonts/noto-sans';
import { NotoSansGujarati_400Regular, NotoSansGujarati_500Medium, NotoSansGujarati_700Bold } from '@expo-google-fonts/noto-sans-gujarati';
import { NotoSansDevanagari_400Regular, NotoSansDevanagari_500Medium, NotoSansDevanagari_700Bold } from '@expo-google-fonts/noto-sans-devanagari';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/store/auth';
import { ToastHost } from '@/components/ui';
import { colors } from '@/theme';
import { detectLanguage } from '@/i18n';

void SplashScreen.preventAutoHideAsync();

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 15_000, refetchOnReconnect: true }, mutations: { retry: 0 } },
});

export default function RootLayout() {
  const { t, i18n } = useTranslation();
  const [fontsLoaded] = useFonts({
    NotoSans_400Regular, NotoSans_500Medium, NotoSans_700Bold,
    NotoSansGujarati_400Regular, NotoSansGujarati_500Medium, NotoSansGujarati_700Bold,
    NotoSansDevanagari_400Regular, NotoSansDevanagari_500Medium, NotoSansDevanagari_700Bold,
  });
  const { ready, accessToken, user, locale, hydrate } = useAuth();

  useEffect(() => { void hydrate(); }, [hydrate]);
  useEffect(() => {
    const lang = locale ?? user?.locale ?? detectLanguage();
    if (lang && lang !== i18n.language) void i18n.changeLanguage(lang);
  }, [locale, user?.locale, i18n]);
  useEffect(() => { if (fontsLoaded && ready) void SplashScreen.hideAsync(); }, [fontsLoaded, ready]);

  if (!fontsLoaded || !ready) return null;
  const loggedIn = !!accessToken;

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <StatusBar style="dark" />
        <Stack
          screenOptions={{
            headerStyle: { backgroundColor: colors.card }, headerTintColor: colors.text, headerShadowVisible: false,
            headerTitleStyle: { fontFamily: i18n.language === 'gu' ? 'NotoSansGujarati_700Bold' : i18n.language === 'hi' ? 'NotoSansDevanagari_700Bold' : 'NotoSans_700Bold' },
            contentStyle: { backgroundColor: colors.bg }, headerBackButtonDisplayMode: 'minimal',
          }}
        >
          <Stack.Protected guard={!loggedIn}>
            <Stack.Screen name="(auth)" options={{ headerShown: false }} />
          </Stack.Protected>
          <Stack.Protected guard={loggedIn}>
            <Stack.Screen name="index" options={{ headerShown: false }} />
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="profile-setup" options={{ title: t('auth.yourName') }} />
            <Stack.Screen name="onboarding" options={{ headerShown: false }} />
            <Stack.Screen name="join" options={{ title: t('join.title') }} />
            <Stack.Screen name="create-society" options={{ title: t('createSociety.title') }} />
            <Stack.Screen name="settings" options={{ title: t('settings.title') }} />
            <Stack.Screen name="orders" options={{ title: t('order.myOrders') }} />
            <Stack.Screen name="event/[id]/index" options={{ title: '' }} />
            <Stack.Screen name="event/[id]/buy" options={{ title: t('buy.title') }} />
            <Stack.Screen name="order/[id]" options={{ title: t('order.status') }} />
            <Stack.Screen name="pass/[id]" options={{ title: t('passes.title'), presentation: 'modal' }} />
            <Stack.Screen name="manage/events" options={{ title: t('manage.events') }} />
            <Stack.Screen name="manage/event-form" options={{ title: t('eventForm.createTitle') }} />
            <Stack.Screen name="manage/event/[id]" options={{ title: t('manage.events') }} />
            <Stack.Screen name="manage/report/[id]" options={{ title: t('report.title') }} />
            <Stack.Screen name="manage/approvals/index" options={{ title: t('approvals.title') }} />
            <Stack.Screen name="manage/approvals/[id]" options={{ title: t('approvals.title') }} />
            <Stack.Screen name="manage/members" options={{ title: t('members.title') }} />
            <Stack.Screen name="manage/moderation" options={{ title: t('moderation.title') }} />
            <Stack.Screen name="manage/invite" options={{ title: t('invite.title') }} />
            <Stack.Screen name="manage/society" options={{ title: t('manage.settings') }} />
          </Stack.Protected>
        </Stack>
        <ToastHost />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
