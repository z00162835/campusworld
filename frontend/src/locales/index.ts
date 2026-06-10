/**
 * vue-i18n configuration
 */
import { createI18n } from 'vue-i18n'
import zh from './zh'
import en from './en'

const getInitialLocale = () => {
  if (typeof window === 'undefined') return 'zh'
  try {
    return window.localStorage.getItem('locale') || 'zh'
  } catch {
    return 'zh'
  }
}

const i18n = createI18n({
  legacy: false,
  locale: getInitialLocale(),
  fallbackLocale: 'en',
  messages: {
    zh,
    en,
  },
})

export default i18n
