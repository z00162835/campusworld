export const CSRF_COOKIE_NAME = 'csrf_token'
export const CSRF_HEADER_NAME = 'X-CSRF-Token'

export function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  const encodedName = `${encodeURIComponent(name)}=`
  const cookie = document.cookie
    .split(';')
    .map(part => part.trim())
    .find(part => part.startsWith(encodedName))
  if (!cookie) return null
  return decodeURIComponent(cookie.slice(encodedName.length))
}

export function readCsrfToken(): string | null {
  return readCookie(CSRF_COOKIE_NAME)
}

export function csrfHeaders(token = readCsrfToken()): Record<string, string> {
  return token ? { [CSRF_HEADER_NAME]: token } : {}
}
