import { useSyncExternalStore } from 'react';
import { NavLink, Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { api, session } from './api';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Societies from './pages/Societies';
import Flagged from './pages/Flagged';
import Audit from './pages/Audit';

function useSession() {
  return useSyncExternalStore(
    (cb) => { window.addEventListener('sp-session', cb); window.addEventListener('storage', cb); return () => { window.removeEventListener('sp-session', cb); window.removeEventListener('storage', cb); }; },
    () => localStorage.getItem('sp_admin_session'),
  );
}

function Layout() {
  const qc = useQueryClient();
  const raw = useSession();
  const user = raw ? JSON.parse(raw).user : null;
  const link = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'}`;
  const logout = async () => {
    const s = session.get();
    if (s) await api('/auth/logout', { method: 'POST', body: { refresh_token: s.refresh_token }, auth: false }).catch(() => undefined);
    session.set(null);
    qc.clear();
  };
  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-slate-200 bg-white p-4 md:flex">
        <div className="mb-6 flex items-center gap-2 px-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-600 text-lg text-white">🎟</div>
          <div><div className="font-semibold leading-tight">SocietyPass</div><div className="text-xs text-slate-500">Platform admin</div></div>
        </div>
        <nav className="flex flex-col gap-1">
          <NavLink to="/" end className={link}>📊 Dashboard</NavLink>
          <NavLink to="/societies" className={link}>🏢 Societies</NavLink>
          <NavLink to="/flagged" className={link}>🚩 Flagged orders</NavLink>
          <NavLink to="/audit" className={link}>📜 Audit logs</NavLink>
        </nav>
        <div className="mt-auto border-t border-slate-100 pt-4 text-sm">
          <div className="truncate font-medium">{user?.name ?? 'Platform admin'}</div>
          <div className="truncate text-xs text-slate-500">{user?.phone}</div>
          <button onClick={logout} className="mt-2 text-xs font-medium text-brand-700 hover:underline">Sign out</button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-4 md:p-8">
        <nav className="mb-4 flex gap-2 overflow-x-auto md:hidden">
          {[['/', 'Dashboard'], ['/societies', 'Societies'], ['/flagged', 'Flagged'], ['/audit', 'Audit']].map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/'} className={link}>{label}</NavLink>
          ))}
          <button onClick={logout} className="ml-auto text-xs font-medium text-brand-700">Sign out</button>
        </nav>
        <Outlet />
      </main>
    </div>
  );
}

export default function App() {
  const raw = useSession();
  const authed = !!raw && JSON.parse(raw).user?.is_super_admin;
  if (!authed) return <Routes><Route path="*" element={<Login />} /></Routes>;
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="societies" element={<Societies />} />
        <Route path="flagged" element={<Flagged />} />
        <Route path="audit" element={<Audit />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
