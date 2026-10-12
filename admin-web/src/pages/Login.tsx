import { type FormEvent, useState } from 'react';
import { ApiError, api, session, type User } from '../api';
import { normalizePhone } from '../format';
import { Button } from '../components/ui';

type Tokens = { access_token: string; refresh_token: string; user: User };

export default function Login() {
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [step, setStep] = useState<'phone' | 'code'>('phone');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [hint, setHint] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (step === 'phone') {
        const res = await api<{ dev_otp?: string | null }>('/auth/otp/request', { method: 'POST', body: { phone: normalizePhone(phone) }, auth: false });
        if (res.dev_otp) { setHint(`Dev code: ${res.dev_otp}`); setCode(res.dev_otp); }
        setStep('code');
      } else {
        const tokens = await api<Tokens>('/auth/otp/verify', { method: 'POST', body: { phone: normalizePhone(phone), code }, auth: false });
        if (!tokens.user.is_super_admin) throw new ApiError(403, 'not_admin', 'This number is not a platform administrator.');
        session.set(tokens);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-600 to-brand-700 p-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-2xl bg-white p-8 shadow-xl">
        <div className="text-center">
          <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-600 text-2xl text-white">🎟</div>
          <h1 className="text-xl font-semibold">SocietyPass admin</h1>
          <p className="text-sm text-slate-500">Platform administrators only</p>
        </div>
        <label className="block text-sm font-medium text-slate-700">Mobile number
          <input value={phone} onChange={(e) => setPhone(e.target.value)} disabled={step === 'code'} inputMode="tel" autoFocus placeholder="98765 43210"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 disabled:bg-slate-50" />
        </label>
        {step === 'code' && (
          <label className="block text-sm font-medium text-slate-700">6-digit code
            <input value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric" autoFocus
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-center text-lg tracking-widest" />
          </label>
        )}
        {hint && <p className="rounded bg-sky-50 px-3 py-2 text-xs text-sky-700">{hint}</p>}
        {error && <p role="alert" className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <Button type="submit" disabled={busy || (step === 'phone' ? phone.length < 10 : code.length < 6)} className="w-full">
          {busy ? 'Please wait…' : step === 'phone' ? 'Send code' : 'Sign in'}
        </Button>
        {step === 'code' && <button type="button" onClick={() => { setStep('phone'); setCode(''); setHint(null); }} className="w-full text-center text-xs text-slate-500 hover:underline">Use a different number</button>}
      </form>
    </div>
  );
}
