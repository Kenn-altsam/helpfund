import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Import translation files
import ruTranslations from './locales/ru.json';
import kzTranslations from './locales/kz.json';
import enTranslations from './locales/en.json';

const resources = {
  ru: {
    translation: ruTranslations,
  },
  kz: {
    translation: kzTranslations,
  },
  en: {
    translation: enTranslations,
  },
};

i18n
  .use(initReactI18next)
  .use(LanguageDetector)
  .init({
    resources,
    lng: localStorage.getItem('helpfund-language') || 'ru', // Default language
    fallbackLng: 'ru',
    interpolation: {
      escapeValue: false,
    },
    react: {
      useSuspense: true,
    },
  });

export default i18n;