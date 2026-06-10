import { describe, expect, it } from 'vitest'
import { getSelectOptionLabel, WORLD_STATUS_OPTIONS, type SelectOption } from './space'

describe('space select option labels', () => {
  const t = (key: string) => `translated:${key}`

  it('prefers i18n label keys for built-in options', () => {
    expect(getSelectOptionLabel(WORLD_STATUS_OPTIONS[0], t)).toBe('translated:spaces.options.status.active')
  })

  it('falls back to legacy labels and raw values for compatibility', () => {
    expect(getSelectOptionLabel({ label: 'Legacy', value: 'legacy' }, t)).toBe('Legacy')
    expect(getSelectOptionLabel({ value: 'raw' } as SelectOption, t)).toBe('raw')
  })
})
