/**
 * 主题管理工具
 * 支持动态切换主题
 */

export type Theme = 'dark' | 'light'

const THEME_KEY = 'app-theme'
const DEFAULT_THEME: Theme = 'dark'

/**
 * 获取当前主题
 */
export function getTheme(): Theme {
  if (typeof window === 'undefined') return DEFAULT_THEME
  
  const stored = localStorage.getItem(THEME_KEY) as Theme
  return stored || DEFAULT_THEME
}

/**
 * 设置主题
 */
export function setTheme(theme: Theme): void {
  if (typeof window === 'undefined') return
  
  localStorage.setItem(THEME_KEY, theme)
  document.documentElement.setAttribute('data-theme', theme)
}

/**
 * 初始化主题
 */
export function initTheme(): void {
  if (typeof window === 'undefined') return
  
  const theme = getTheme()
  setTheme(theme)
}

/**
 * 切换主题
 */
export function toggleTheme(): Theme {
  const currentTheme = getTheme()
  const newTheme: Theme = currentTheme === 'dark' ? 'light' : 'dark'
  setTheme(newTheme)
  return newTheme
}

