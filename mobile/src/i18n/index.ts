import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import * as Localization from 'expo-localization';
import en from './en';
import gu from './gu';
import hi from './hi';

export const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'gu', label: 'ગુજરાતી' },
  { code: 'hi', label: 'हिन्दी' },
] as const;

export function detectLanguage(): 'en' | 'gu' | 'hi' {
  const code = Localization.getLocales()[0]?.languageCode;
  return code === 'gu' || code === 'hi' ? code : 'en';
}

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, gu: { translation: gu }, hi: { translation: hi } },
  lng: detectLanguage(),
  fallbackLng: 'en', // untranslated gu/hi keys fall back to the (complete) English strings
  interpolation: { escapeValue: false },
  returnNull: false,
});

export default i18n;
