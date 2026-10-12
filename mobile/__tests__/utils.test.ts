import { formatINR, priceLabel } from '../src/utils/money';
import { isValidOtp, isValidUpiId, isValidUtr, normalizeIndianPhone, sanitizeUtr } from '../src/utils/validation';
import { parseInviteCode } from '../src/utils/deepLink';
import { assignableRoles, canScan, isAdmin, tabsForRole } from '../src/utils/roles';
import { formatCountdown, formatDateRange, parseDay, toDayString } from '../src/utils/dates';
import { clearPasses, loadPasses, savePasses, KeyValueStore } from '../src/utils/passCache';
import { buildUpiUri } from '../src/utils/upi';

describe('money', () => {
  it('uses Indian digit grouping', () => {
    expect(formatINR(0)).toBe('₹0');
    expect(formatINR(500)).toBe('₹500');
    expect(formatINR(1500)).toBe('₹1,500');
    expect(formatINR(123456)).toBe('₹1,23,456');
    expect(formatINR(1234567)).toBe('₹12,34,567');
    expect(formatINR(-2500)).toBe('-₹2,500');
  });
  it('labels free tiers', () => {
    expect(priceLabel(0)).toBe('Free');
    expect(priceLabel(300)).toBe('₹300');
  });
});

describe('validation', () => {
  it('normalises Indian phone numbers', () => {
    expect(normalizeIndianPhone('98765 43210')).toBe('9876543210');
    expect(normalizeIndianPhone('+91 98765-43210')).toBe('9876543210');
    expect(normalizeIndianPhone('09876543210')).toBe('9876543210');
    expect(normalizeIndianPhone('12345')).toBeNull();
    expect(normalizeIndianPhone('5876543210')).toBeNull(); // must start 6-9
  });
  it('validates UTR as exactly 12 digits', () => {
    expect(isValidUtr('402611223344')).toBe(true);
    expect(isValidUtr('4026 1122 3344')).toBe(true);
    expect(isValidUtr('40261122334')).toBe(false);
    expect(isValidUtr('40261122334A')).toBe(false);
    expect(sanitizeUtr('40a26-11223344999')).toBe('402611223344');
  });
  it('validates UPI ids and OTPs', () => {
    expect(isValidUpiId('greenvalley@okhdfc')).toBe(true);
    expect(isValidUpiId('not-a-upi')).toBe(false);
    expect(isValidOtp('123456')).toBe(true);
    expect(isValidOtp('12345')).toBe(false);
  });
});

describe('invite links', () => {
  it('parses deep links, web links and bare codes', () => {
    expect(parseInviteCode('societypass://join?code=abcd2345')).toBe('ABCD2345');
    expect(parseInviteCode('https://societypass.app/join/ABCD2345')).toBe('ABCD2345');
    expect(parseInviteCode(' abcd2345 ')).toBe('ABCD2345');
    expect(parseInviteCode('https://example.com/nothing')).toBeNull();
    expect(parseInviteCode('')).toBeNull();
  });
});

describe('roles', () => {
  it('shows tabs by role', () => {
    expect(tabsForRole('member')).toEqual(['index', 'passes', 'gallery']);
    expect(tabsForRole('volunteer')).toEqual(['index', 'passes', 'gallery', 'scan']);
    expect(tabsForRole('admin')).toEqual(['index', 'passes', 'gallery', 'scan', 'manage']);
    expect(tabsForRole('owner')).toContain('manage');
    expect(tabsForRole(undefined)).toEqual(['index', 'passes', 'gallery']);
  });
  it('mirrors the server permission helpers', () => {
    expect(isAdmin('admin')).toBe(true);
    expect(isAdmin('volunteer')).toBe(false);
    expect(canScan('volunteer')).toBe(true);
    expect(canScan('member')).toBe(false);
  });
  it('computes assignable roles like the server', () => {
    expect(assignableRoles('owner', 'member')).toEqual(['admin', 'volunteer']);
    expect(assignableRoles('admin', 'member')).toEqual(['volunteer']);
    expect(assignableRoles('admin', 'admin')).toEqual([]);
    expect(assignableRoles('owner', 'owner')).toEqual([]);
    expect(assignableRoles('volunteer', 'member')).toEqual([]);
  });
});

describe('dates', () => {
  it('round-trips plain day strings without timezone drift', () => {
    expect(toDayString(parseDay('2026-10-12'))).toBe('2026-10-12');
    expect(parseDay('2026-03-01').getDate()).toBe(1);
  });
  it('formats ranges', () => {
    expect(formatDateRange('2026-10-12T10:00:00', '2026-10-12T20:00:00', 'en-IN')).toMatch(/12/);
    expect(formatDateRange('2026-10-12T10:00:00', '2026-10-20T20:00:00', 'en-IN')).toMatch(/12 –/);
  });
  it('formats the expiry countdown', () => {
    const now = Date.parse('2026-10-12T00:00:00Z');
    expect(formatCountdown('2026-10-12T00:23:00Z', now)).toBe('23m');
    expect(formatCountdown('2026-10-12T05:05:00Z', now)).toBe('5h 05m');
    expect(formatCountdown('2026-10-11T23:00:00Z', now)).toBe('expired');
  });
});

describe('pass cache (offline)', () => {
  const memory = (): KeyValueStore => {
    const m = new Map<string, string>();
    return {
      getItem: async (k) => m.get(k) ?? null,
      setItem: async (k, v) => void m.set(k, v),
      removeItem: async (k) => void m.delete(k),
    };
  };
  it('saves and loads passes per user', async () => {
    const store = memory();
    await savePasses(store, 'u1', [{ id: 'p1', qr_token: 'v1.a.b' }]);
    const cached = await loadPasses<{ id: string; qr_token: string }>(store, 'u1');
    expect(cached?.passes[0].qr_token).toBe('v1.a.b');
    expect(await loadPasses(store, 'u2')).toBeNull(); // never leak another user's passes
    await clearPasses(store, 'u1');
    expect(await loadPasses(store, 'u1')).toBeNull();
  });
  it('treats corrupt cache as empty', async () => {
    const store = memory();
    await store.setItem('passes:v1:u1', '{not json');
    expect(await loadPasses(store, 'u1')).toBeNull();
  });
});

describe('upi', () => {
  it('builds a pay link with the order reference as the note', () => {
    const uri = buildUpiUri({ pa: 'society@okhdfc', pn: 'Green Valley', am: 1000, tn: 'Order SP-ABCD2345' });
    expect(uri).toBe('upi://pay?pa=society%40okhdfc&pn=Green%20Valley&am=1000.00&cu=INR&tn=Order%20SP-ABCD2345');
  });
});
