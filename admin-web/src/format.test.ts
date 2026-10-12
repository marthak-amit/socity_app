import { describe, expect, it } from 'vitest';
import { formatINR, normalizePhone, timeAgo } from './format';

describe('format', () => {
  it('groups rupees the Indian way', () => {
    expect(formatINR(0)).toBe('₹0');
    expect(formatINR(1500)).toBe('₹1,500');
    expect(formatINR(1234567)).toBe('₹12,34,567');
  });
  it('normalises phones', () => {
    expect(normalizePhone('98765 43210')).toBe('+919876543210');
    expect(normalizePhone('09876543210')).toBe('+919876543210');
    expect(normalizePhone('+14155550123')).toBe('+14155550123');
  });
  it('prints relative times', () => {
    const now = Date.parse('2026-10-12T12:00:00Z');
    expect(timeAgo('2026-10-12T11:59:40Z', now)).toBe('just now');
    expect(timeAgo('2026-10-12T11:30:00Z', now)).toBe('30m ago');
    expect(timeAgo('2026-10-10T12:00:00Z', now)).toBe('2d ago');
  });
});
