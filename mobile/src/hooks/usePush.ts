import { useEffect } from 'react';
import { Platform } from 'react-native';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import Constants from 'expo-constants';
import { router } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import { post } from '@/api/client';
import { useAuth } from '@/store/auth';

Notifications.setNotificationHandler({
  handleNotification: async () => ({ shouldShowBanner: true, shouldShowList: true, shouldPlaySound: true, shouldSetBadge: false }),
});

type PushData = { type?: string; society_id?: string; event_id?: string; order_id?: string };

/** Route a tapped notification to the right screen (switching society first when needed). */
export async function openFromNotification(data: PushData) {
  const { setActiveSociety } = useAuth.getState();
  if (data.society_id) await setActiveSociety(data.society_id);
  switch (data.type) {
    case 'order_approved': router.push('/(tabs)/passes'); break;
    case 'order_rejected': if (data.order_id) router.push(`/order/${data.order_id}`); break;
    case 'event_published': case 'event_reminder': case 'event_cancelled':
      if (data.event_id) router.push(`/event/${data.event_id}`); break;
    case 'join_request': router.push('/manage/members'); break;
    case 'gallery_pending': router.push('/manage/moderation'); break;
    case 'volunteer_assigned': router.push('/(tabs)/scan'); break;
    default: router.push('/');
  }
}

export async function registerForPush(): Promise<string | null> {
  try {
    if (!Device.isDevice) return null; // simulators can't receive pushes
    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync('default', { name: 'Default', importance: Notifications.AndroidImportance.MAX });
    }
    const existing = await Notifications.getPermissionsAsync();
    let status = existing.status;
    if (status !== 'granted') status = (await Notifications.requestPermissionsAsync()).status;
    if (status !== 'granted') return null;
    const projectId = Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
    const token = (await Notifications.getExpoPushTokenAsync(projectId ? { projectId } : undefined)).data;
    await post('/me/push-tokens', { token, platform: Platform.OS });
    return token;
  } catch {
    return null; // push is best-effort (Expo Go on Android SDK 53+ has no push support; needs a dev build)
  }
}

/** Registers the device token once signed in, refreshes data when a push arrives, and handles taps. */
export function usePushRegistration() {
  const qc = useQueryClient();
  const token = useAuth((s) => s.accessToken);
  useEffect(() => {
    if (!token) return;
    void registerForPush();
    const received = Notifications.addNotificationReceivedListener(() => { void qc.invalidateQueries(); });
    const tapped = Notifications.addNotificationResponseReceivedListener((r) => {
      void qc.invalidateQueries();
      void openFromNotification((r.notification.request.content.data ?? {}) as PushData);
    });
    return () => { received.remove(); tapped.remove(); };
  }, [token, qc]);
}
