import { describe, expect, it } from 'vitest'
import { routes } from './index'

describe('router i18n metadata', () => {
  it('uses titleKey metadata for all routes instead of literal titles', () => {
    for (const route of routes) {
      expect(route.meta?.title).toBeUndefined()
      expect(route.meta?.titleKey).toEqual(expect.any(String))
    }
  })
})
