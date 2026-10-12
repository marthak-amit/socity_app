/** Normalise what a user typed into an Indian mobile number (10 digits), or null if invalid. */
export function normalizeIndianPhone(input: string): string | null {
  const digits = input.replace(/[^\d]/g, '');
  const local = digits.length === 12 && digits.startsWith('91') ? digits.slice(2) : digits.length === 11 && digits.startsWith('0') ? digits.slice(1) : digits;
  return /^[6-9]\d{9}$/.test(local) ? local : null;
}

export const UTR_LENGTH = 12;

/** Keep digits only, max 12 (UPI reference numbers are 12 digits). */
export function sanitizeUtr(input: string): string {
  return input.replace(/\D/g, '').slice(0, UTR_LENGTH);
}

export function isValidUtr(input: string): boolean {
  return /^\d{12}$/.test(input.replace(/\s+/g, ''));
}

export function isValidUpiId(v: string): boolean {
  return /^[A-Za-z0-9.\-_]{1,64}@[A-Za-z][A-Za-z0-9]{1,31}$/.test(v.trim());
}

export function isValidOtp(v: string): boolean {
  return /^\d{6}$/.test(v);
}
