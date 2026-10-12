export type Role = 'owner' | 'admin' | 'volunteer' | 'member';

const RANK: Record<Role, number> = { member: 1, volunteer: 2, admin: 3, owner: 4 };

export const atLeast = (role: Role | undefined, min: Role): boolean => !!role && RANK[role] >= RANK[min];
export const isAdmin = (role?: Role) => atLeast(role, 'admin');
export const canScan = (role?: Role) => atLeast(role, 'volunteer');

export type TabKey = 'index' | 'passes' | 'gallery' | 'scan' | 'manage';

/** Which bottom tabs a role sees. (The server enforces the same rules — this is UX only.) */
export function tabsForRole(role?: Role): TabKey[] {
  const tabs: TabKey[] = ['index', 'passes', 'gallery'];
  if (canScan(role)) tabs.push('scan');
  if (isAdmin(role)) tabs.push('manage');
  return tabs;
}

/** Roles the actor may assign to / remove from the target (mirrors the server rules). */
export function assignableRoles(actor: Role | undefined, target: Role): Role[] {
  if (target === 'owner') return [];
  if (actor === 'owner') return ['admin', 'volunteer', 'member'].filter((r) => r !== target) as Role[];
  if (actor === 'admin' && (target === 'member' || target === 'volunteer')) {
    return ['volunteer', 'member'].filter((r) => r !== target) as Role[];
  }
  return [];
}
