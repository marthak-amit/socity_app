import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { get } from '@/api/client';
import type { Me, Membership, Society } from '@/api/types';
import { useAuth } from '@/store/auth';
import type { Role } from '@/utils/roles';

export const qk = {
  me: ['me'] as const,
  society: (id?: string | null) => ['society', id] as const,
};

export function useMe() {
  const token = useAuth((s) => s.accessToken);
  return useQuery({ queryKey: qk.me, queryFn: () => get<Me>('/me'), enabled: !!token, staleTime: 30_000 });
}

/** Resolves the active society + the caller's role in it (from the server's membership, never user input). */
export function useActiveSociety() {
  const me = useMe();
  const activeId = useAuth((s) => s.activeSocietyId);
  const setActive = useAuth((s) => s.setActiveSociety);
  const memberships = me.data?.memberships ?? [];
  const activeMemberships = memberships.filter((m) => m.status === 'active');
  const current: Membership | undefined = activeMemberships.find((m) => m.society.id === activeId) ?? activeMemberships[0];

  useEffect(() => {
    if (me.data && current && current.society.id !== activeId) void setActive(current.society.id);
    if (me.data && !current && activeId) void setActive(null);
  }, [me.data, current, activeId, setActive]);

  return {
    isLoading: me.isLoading, isError: me.isError, error: me.error, refetch: me.refetch,
    memberships, pending: memberships.filter((m) => m.status === 'pending'),
    societyId: current?.society.id as string | undefined, membership: current, role: current?.role as Role | undefined,
    society: current?.society, suspended: current?.society.status === 'suspended', user: me.data?.user,
  };
}

export function useSocietyDetail(societyId?: string) {
  return useQuery({ queryKey: qk.society(societyId), queryFn: () => get<Society>(`/societies/${societyId}`), enabled: !!societyId });
}
