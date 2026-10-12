import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import type { User } from '@/api/types';

const K = { access: 'sp_access', refresh: 'sp_refresh', user: 'sp_user', society: 'sp_society', locale: 'sp_locale' };

type AuthState = {
  ready: boolean;
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  activeSocietyId: string | null;
  locale: string | null;
  hydrate: () => Promise<void>;
  setSession: (access: string, refresh: string, user: User) => Promise<void>;
  setUser: (user: User) => Promise<void>;
  logout: () => Promise<void>;
  setActiveSociety: (id: string | null) => Promise<void>;
  setLocale: (l: string) => Promise<void>;
};

export const useAuth = create<AuthState>((set, get) => ({
  ready: false, accessToken: null, refreshToken: null, user: null, activeSocietyId: null, locale: null,
  async hydrate() {
    try {
      const [access, refresh, user, society, locale] = await Promise.all([
        SecureStore.getItemAsync(K.access), SecureStore.getItemAsync(K.refresh), AsyncStorage.getItem(K.user),
        AsyncStorage.getItem(K.society), AsyncStorage.getItem(K.locale),
      ]);
      set({ accessToken: access, refreshToken: refresh, user: user ? JSON.parse(user) : null, activeSocietyId: society, locale, ready: true });
    } catch {
      set({ ready: true });
    }
  },
  async setSession(access, refresh, user) {
    await Promise.all([SecureStore.setItemAsync(K.access, access), SecureStore.setItemAsync(K.refresh, refresh), AsyncStorage.setItem(K.user, JSON.stringify(user))]);
    set({ accessToken: access, refreshToken: refresh, user });
  },
  async setUser(user) {
    await AsyncStorage.setItem(K.user, JSON.stringify(user));
    set({ user });
  },
  async logout() {
    const refresh = get().refreshToken;
    set({ accessToken: null, refreshToken: null, user: null, activeSocietyId: null });
    await Promise.all([SecureStore.deleteItemAsync(K.access), SecureStore.deleteItemAsync(K.refresh), AsyncStorage.multiRemove([K.user, K.society])]);
    if (refresh) { // best effort: revoke server-side
      try {
        const { apiBase } = await import('@/api/client');
        await fetch(`${apiBase()}/auth/logout`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: refresh }) });
      } catch { /* offline */ }
    }
  },
  async setActiveSociety(id) {
    set({ activeSocietyId: id });
    if (id) await AsyncStorage.setItem(K.society, id); else await AsyncStorage.removeItem(K.society);
  },
  async setLocale(l) {
    set({ locale: l });
    await AsyncStorage.setItem(K.locale, l);
  },
}));
