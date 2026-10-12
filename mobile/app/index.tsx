import React from 'react';
import { Redirect } from 'expo-router';
import { ErrorState, LoadingView } from '@/components/ui';
import { useActiveSociety } from '@/hooks/useSociety';
import { useAuth } from '@/store/auth';

/** Entry router for signed-in users: name → onboarding (no society yet) → tabs. */
export default function Index() {
  const user = useAuth((s) => s.user);
  const { isLoading, isError, error, refetch, societyId } = useActiveSociety();
  if (!user?.name) return <Redirect href="/profile-setup" />;
  if (isLoading) return <LoadingView />;
  if (isError) return <ErrorState error={error} onRetry={refetch} />;
  return <Redirect href={societyId ? '/(tabs)' : '/onboarding'} />;
}
