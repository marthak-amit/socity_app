import fs from 'fs';
import path from 'path';
import en from '../src/i18n/en';
import hi from '../src/i18n/hi';
import gu from '../src/i18n/gu';

type Tree = { [k: string]: string | Tree };
const flatten = (obj: Tree, prefix = ''): Record<string, string> =>
  Object.entries(obj).reduce((acc, [k, v]) => {
    const key = prefix ? `${prefix}.${k}` : k;
    return typeof v === 'string' ? { ...acc, [key]: v } : { ...acc, ...flatten(v, key) };
  }, {} as Record<string, string>);

const EN = flatten(en as unknown as Tree);

function sourceFiles(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) return e.name === 'node_modules' || e.name === 'i18n' ? [] : sourceFiles(p);
    return /\.tsx?$/.test(e.name) ? [p] : [];
  });
}

describe('i18n', () => {
  it('every static t("key") used in the app exists in the English file', () => {
    const root = path.join(__dirname, '..');
    const files = [...sourceFiles(path.join(root, 'app')), ...sourceFiles(path.join(root, 'src'))];
    const missing: string[] = [];
    for (const f of files) {
      const text = fs.readFileSync(f, 'utf8');
      for (const m of text.matchAll(/\bt\(\s*['"`]([a-zA-Z0-9_.]+)['"`]/g)) {
        const key = m[1];
        // dynamic prefixes like t(`scan.result.${r}`) are checked by the loop below, skip partials
        if (!(key in EN)) missing.push(`${path.relative(root, f)}: ${key}`);
      }
    }
    expect(missing).toEqual([]);
  });

  it('has every key that is looked up dynamically (t(`group.${value}`))', () => {
    const need: Record<string, string[]> = {
      roles: ['owner', 'admin', 'volunteer', 'member'],
      common: ['pending', 'approved', 'rejected', 'cancelled'],
      'scan.result': ['ok', 'already_scanned', 'invalid_token', 'wrong_event', 'pass_revoked', 'event_not_active', 'not_event_day', 'tier_not_valid_today'],
      'approvals.flag': ['duplicate_utr', 'amount_mismatch', 'missing_utr'],
      'approvals.flagHelp': ['duplicate_utr', 'amount_mismatch', 'missing_utr'],
      'manage.warnings': ['min_two_admins', 'upi_not_configured'],
      'eventAdmin.statusLabel': ['draft', 'published', 'closed', 'cancelled'],
    };
    const missing = Object.entries(need).flatMap(([group, keys]) => keys.map((k) => `${group}.${k}`)).filter((k) => !(k in EN));
    expect(missing).toEqual([]);
  });

  it('Hindi and Gujarati only define keys that exist in English (no typos)', () => {
    for (const [name, tree] of [['hi', hi], ['gu', gu]] as const) {
      const extra = Object.keys(flatten(tree as unknown as Tree)).filter((k) => !(k in EN));
      expect({ name, extra }).toEqual({ name, extra: [] });
    }
  });

  it('keeps interpolation placeholders consistent across languages', () => {
    for (const tree of [hi, gu]) {
      for (const [k, v] of Object.entries(flatten(tree as unknown as Tree))) {
        const ph = (s: string) => (s.match(/\{\{\w+\}\}/g) ?? []).sort().join();
        expect({ k, ph: ph(v) }).toEqual({ k, ph: ph(EN[k]) });
      }
    }
  });
});
