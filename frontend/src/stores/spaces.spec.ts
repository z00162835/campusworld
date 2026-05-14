import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useSpacesStore } from './spaces'
import { spacesApi } from '@/api/spaces'

vi.mock('@/api/spaces', () => ({
  spacesApi: {
    getSpaces: vi.fn(),
  },
}))

const responseFor = (name: string) => ({
  data: {
    items: [{
      id: name === 'old' ? 1 : 2,
      uuid: name,
      type_code: 'world',
      name,
      description: '',
      is_active: true,
      is_public: true,
      access_level: 'public',
      trait_class: 'SPACE',
      trait_mask: 516,
      attributes: {},
      tags: [],
      created_at: '',
      updated_at: '',
    }],
    page: { total: 1, offset: 0, limit: 24 },
  },
})

describe('spaces store request ordering', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(spacesApi.getSpaces).mockReset()
  })

  it('ignores stale responses from earlier fetches', async () => {
    let resolveOld: (value: unknown) => void = () => {}
    let resolveNew: (value: unknown) => void = () => {}
    vi.mocked(spacesApi.getSpaces)
      .mockReturnValueOnce(new Promise(resolve => { resolveOld = resolve }) as any)
      .mockReturnValueOnce(new Promise(resolve => { resolveNew = resolve }) as any)

    const store = useSpacesStore()
    const oldRequest = store.fetchSpaces('world')
    const newRequest = store.fetchSpaces('world')

    resolveNew(responseFor('new'))
    await newRequest
    expect(store.nodes.world.map(node => node.name)).toEqual(['new'])
    expect(store.loading).toBe(false)

    resolveOld(responseFor('old'))
    await oldRequest
    expect(store.nodes.world.map(node => node.name)).toEqual(['new'])
  })
})
