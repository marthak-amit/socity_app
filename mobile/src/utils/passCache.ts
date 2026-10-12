/** Offline cache for "My Passes" so QR codes still render with no signal. Storage is injected for testability. */
export interface KeyValueStore {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
}

export interface CachedPasses<T> {
  savedAt: string;
  passes: T[];
}

const key = (userId: string) => `passes:v1:${userId}`;

export async function savePasses<T>(store: KeyValueStore, userId: string, passes: T[]): Promise<void> {
  const payload: CachedPasses<T> = { savedAt: new Date().toISOString(), passes };
  await store.setItem(key(userId), JSON.stringify(payload));
}

export async function loadPasses<T>(store: KeyValueStore, userId: string): Promise<CachedPasses<T> | null> {
  try {
    const raw = await store.getItem(key(userId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CachedPasses<T>;
    return Array.isArray(parsed.passes) ? parsed : null;
  } catch {
    return null; // corrupt cache is treated as empty
  }
}

export async function clearPasses(store: KeyValueStore, userId: string): Promise<void> {
  await store.removeItem(key(userId));
}
