export const colors = {
  primary: '#4F46E5', primaryDark: '#3730A3', primarySoft: '#EEF2FF',
  bg: '#F6F7FB', card: '#FFFFFF', border: '#E5E7EB', text: '#111827', muted: '#6B7280', faint: '#9CA3AF',
  success: '#16A34A', successSoft: '#DCFCE7', danger: '#DC2626', dangerSoft: '#FEE2E2',
  warning: '#D97706', warningSoft: '#FEF3C7', info: '#0284C7', infoSoft: '#E0F2FE',
};
export const radius = { sm: 8, md: 12, lg: 16, xl: 24, pill: 999 };
export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 };
export const shadow = {
  shadowColor: '#0F172A', shadowOpacity: 0.06, shadowRadius: 10, shadowOffset: { width: 0, height: 3 }, elevation: 2,
};

/** Font family per UI language (Noto Sans covers Latin; the Gujarati / Devanagari families cover those scripts). */
export const FONT_FAMILIES = {
  en: { regular: 'NotoSans_400Regular', medium: 'NotoSans_500Medium', bold: 'NotoSans_700Bold' },
  gu: { regular: 'NotoSansGujarati_400Regular', medium: 'NotoSansGujarati_500Medium', bold: 'NotoSansGujarati_700Bold' },
  hi: { regular: 'NotoSansDevanagari_400Regular', medium: 'NotoSansDevanagari_500Medium', bold: 'NotoSansDevanagari_700Bold' },
} as const;
export type Lang = keyof typeof FONT_FAMILIES;
