import AsyncStorage from '@react-native-async-storage/async-storage';
import { useQuery } from '@tanstack/react-query';
import { ApiError, get } from '@/api/client';
import type { Page, PassT } from '@/api/types';
import { useAuth } from '@/store/auth';
import { loadPasses, savePasses } from '@/utils/passCache';

export type PassesResult = { passes: PassT[]; offline: boolean; savedAt: string | null };

async function fetchAllPasses(): Promise<PassT[]> {
  const out: PassT[] = [];
  for (let offset = 0; offset < 1000; offset += 100) {
    const page = await get<Page<PassT>>('/me/passes', { limit: 100, offset });
    out.push(...page.items);
    if (out.length >= page.total) break;
  }
  return out;
}

/** Passes from the API; when there's no connection, falls back to the copy saved on this phone so QR codes still work. */
export function useMyPasses() {
  const userId = useAuth((s) => s.user?.id);
  return useQuery<PassesResult>({
    queryKey: ['passes', userId],
    enabled: !!userId,
    networkMode: 'always',
    queryFn: async () => {
      try {
        const passes = await fetchAllPasses();
        await savePasses(AsyncStorage, userId!, passes);
        return { passes, offline: false, savedAt: null };
      } catch (e) {
        if (e instanceof ApiError && e.code === 'network_error') {
          const cached = await loadPasses<PassT>(AsyncStorage, userId!);
          if (cached) return { passes: cached.passes, offline: true, savedAt: cached.savedAt };
        }
        throw e;
      }
    },
  });
}
