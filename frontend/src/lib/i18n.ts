import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import it from "../locales/it.json";
import en from "../locales/en.json";

export const SUPPORTED_LANGUAGES = ["it", "en"] as const;
export type Language = (typeof SUPPORTED_LANGUAGES)[number];

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      it: { translation: it },
      en: { translation: en },
    },
    fallbackLng: "it",
    supportedLngs: SUPPORTED_LANGUAGES as unknown as string[],
    interpolation: { escapeValue: false },
    detection: {
      // Prefer the value the app persisted; fall back to the browser locale.
      order: ["localStorage", "navigator"],
      lookupLocalStorage: "language",
      caches: ["localStorage"],
    },
  });

/** Change the active UI language and persist the choice. */
export function setLanguage(lang: Language) {
  i18n.changeLanguage(lang);
  localStorage.setItem("language", lang);
}

export default i18n;
