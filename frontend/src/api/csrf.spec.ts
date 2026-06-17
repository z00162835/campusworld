import { afterEach, describe, expect, it } from 'vitest'
import { CSRF_HEADER_NAME, csrfHeaders, readCookie } from './csrf'

describe('CSRF helpers', () => {
  afterEach(() => {
    document.cookie = 'csrf_token=; Max-Age=0; path=/'
  })

  it('reads and decodes cookies by name', () => {
    document.cookie = 'csrf_token=token%20123; path=/'

    expect(readCookie('csrf_token')).toBe('token 123')
  })

  it('builds the CSRF header only when a token is present', () => {
    expect(csrfHeaders(null)).toEqual({})
    expect(csrfHeaders('csrf-value')).toEqual({ [CSRF_HEADER_NAME]: 'csrf-value' })
  })
})
