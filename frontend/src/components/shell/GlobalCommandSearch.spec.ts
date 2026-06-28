import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import GlobalCommandSearch from './GlobalCommandSearch.vue'
import { useWorldMapStore } from '@/stores/worldMap'
import { useWorldSessionStore } from '@/stores/worldSession'

vi.mock('vue-i18n', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-i18n')>()
  return {
    ...actual,
    useI18n: () => ({ t: (key: string) => key }),
  }
})

vi.mock('@/api/semanticMap', () => ({
  semanticMapApi: {
    query: vi.fn(),
    getFocus: vi.fn(),
    executeAction: vi.fn(),
    getSpaceSummary: vi.fn(),
    getEntityInspect: vi.fn(),
  },
}))

describe('GlobalCommandSearch', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('does not search or clear input while sessionActionLoading', async () => {
    const worldSession = useWorldSessionStore()
    worldSession.interactionState = {
      session: { id: 'sess1', currentSpaceId: 'space1' },
      decision_center: { events: [] },
      focus_map: null,
      context_summary: null,
    } as any
    worldSession.sessionActionLoading = true

    const mapStore = useWorldMapStore()
    const searchMap = vi.spyOn(mapStore, 'searchMap').mockResolvedValue({
      mode: 'focus',
      answer: '',
      map_patch: {},
    } as any)

    const wrapper = mount(GlobalCommandSearch, {
      global: {
        stubs: { ElIcon: true, Search: true },
      },
    })

    const input = wrapper.find('input')
    await input.setValue('north gate')
    await input.trigger('keydown.enter')

    expect(searchMap).not.toHaveBeenCalled()
    expect((input.element as HTMLInputElement).value).toBe('north gate')
  })

  it('does not search map when submitQuery is rejected', async () => {
    const worldSession = useWorldSessionStore()
    worldSession.interactionState = null

    const mapStore = useWorldMapStore()
    const searchMap = vi.spyOn(mapStore, 'searchMap').mockResolvedValue({
      mode: 'focus',
      answer: '',
      map_patch: {},
    } as any)

    const wrapper = mount(GlobalCommandSearch, {
      global: {
        stubs: { ElIcon: true, Search: true },
      },
    })

    const input = wrapper.find('input')
    await input.setValue('north gate')
    await input.trigger('keydown.enter')

    expect(searchMap).not.toHaveBeenCalled()
    expect((input.element as HTMLInputElement).value).toBe('north gate')
  })

  it('searches map only after submitQuery accepts', async () => {
    const worldSession = useWorldSessionStore()
    worldSession.interactionState = {
      session: { id: 'sess1', currentSpaceId: 'space1' },
      decision_center: { events: [] },
      focus_map: null,
      context_summary: null,
    } as any

    let releaseCompletion: (() => void) | undefined
    const completion = new Promise<void>(resolve => {
      releaseCompletion = resolve
    })
    vi.spyOn(worldSession, 'submitQuery').mockResolvedValue({
      accepted: true,
      completion,
    })

    const mapStore = useWorldMapStore()
    const searchMap = vi.spyOn(mapStore, 'searchMap').mockResolvedValue({
      mode: 'focus',
      answer: '',
      map_patch: {},
    } as any)

    const wrapper = mount(GlobalCommandSearch, {
      global: {
        stubs: { ElIcon: true, Search: true },
      },
    })

    const input = wrapper.find('input')
    await input.setValue('north gate')
    const submitPromise = input.trigger('keydown.enter')

    await vi.waitFor(() => {
      expect(searchMap).toHaveBeenCalledWith('north gate')
      expect((input.element as HTMLInputElement).value).toBe('')
    })

    releaseCompletion?.()
    await submitPromise
  })
})
