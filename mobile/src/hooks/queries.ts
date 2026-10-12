import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { get } from '@/api/client';
import type { EventT, GalleryItem, Member, Order, OrderSummary, Page, PassT, Report, ScanEvent, Volunteer } from '@/api/types';

/** Flatten an infinite query's pages; `hasNext` mirrors the server's total. */
export function flat<T>(data?: { pages: Page<T>[] }): T[] {
  return data?.pages.flatMap((p) => p.items) ?? [];
}

function nextOffset<T>(last: Page<T>, all: Page<T>[]): number | undefined {
  const loaded = all.reduce((n, p) => n + p.items.length, 0);
  return loaded < last.total ? loaded : undefined;
}

export function usePaged<T>(key: readonly unknown[], path: string | null, query: Record<string, string | number | boolean | undefined> = {}, limit = 20) {
  return useInfiniteQuery({
    queryKey: [...key, query],
    enabled: !!path,
    initialPageParam: 0,
    queryFn: ({ pageParam }) => get<Page<T>>(path!, { ...query, limit, offset: pageParam }),
    getNextPageParam: (last, all) => nextOffset(last, all),
  });
}

export const useEvents = (sid?: string, when: 'upcoming' | 'past' | 'all' = 'upcoming') =>
  usePaged<EventT>(['events', sid], sid ? `/societies/${sid}/events` : null, { when });

export const useEvent = (sid?: string, id?: string) =>
  useQuery({ queryKey: ['event', sid, id], queryFn: () => get<EventT>(`/societies/${sid}/events/${id}`), enabled: !!sid && !!id });

export const useOrder = (sid?: string, id?: string) =>
  useQuery({ queryKey: ['order', sid, id], queryFn: () => get<Order>(`/societies/${sid}/orders/${id}`), enabled: !!sid && !!id });

export const useMyOrders = (sid?: string) => usePaged<Order>(['orders-mine', sid], sid ? `/societies/${sid}/orders/mine` : null);

export const useApprovalQueue = (sid: string | undefined, status: string, eventId?: string, submitted = true) =>
  usePaged<Order>(['approvals', sid], sid ? `/societies/${sid}/orders` : null, { status, event_id: eventId, submitted: status === 'pending' ? submitted : undefined });

export const useOrderSummary = (sid?: string, enabled = true) =>
  useQuery({ queryKey: ['order-summary', sid], queryFn: () => get<OrderSummary>(`/societies/${sid}/orders/summary`), enabled: !!sid && enabled, refetchInterval: 60_000 });

export const useMembers = (sid: string | undefined, status: 'pending' | 'active', q?: string) =>
  usePaged<Member>(['members', sid], sid ? `/societies/${sid}/members` : null, { status, q: q || undefined }, 30);

export const useGallery = (sid: string | undefined, params: { event_id?: string; status?: string; mine?: boolean } = {}) =>
  usePaged<GalleryItem>(['gallery', sid], sid ? `/societies/${sid}/gallery` : null, params, 30);

export const useReport = (sid?: string, eid?: string) =>
  useQuery({ queryKey: ['report', sid, eid], queryFn: () => get<Report>(`/societies/${sid}/events/${eid}/report`), enabled: !!sid && !!eid });

export const useVolunteers = (sid?: string, eid?: string) =>
  useQuery({ queryKey: ['volunteers', sid, eid], queryFn: () => get<Volunteer[]>(`/societies/${sid}/events/${eid}/volunteers`), enabled: !!sid && !!eid });

export const useScanEvents = (sid?: string, enabled = true) =>
  useQuery({ queryKey: ['scan-events', sid], queryFn: () => get<ScanEvent[]>(`/societies/${sid}/scan/events`), enabled: !!sid && enabled, refetchInterval: 30_000 });

export function useInvalidate() {
  const qc = useQueryClient();
  return (...keys: string[]) => Promise.all(keys.map((k) => qc.invalidateQueries({ queryKey: [k] })));
}

export type { PassT };
