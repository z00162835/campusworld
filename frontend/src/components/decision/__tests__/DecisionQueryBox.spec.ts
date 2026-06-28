import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { queryAicoStream } from '@/api/decisionCenter'
import DecisionQueryBox from '../DecisionQueryBox.vue'
import { useWorldSessionStore } from '@/stores/worldSession'

vi.mock('@/api/decisionCenter', () => ({
  decisionCenterApi: {
    query: vi.fn(),
    executeAction: vi.fn(),
    cancelStream: vi.fn(),
  },
  queryAicoStream: vi.fn(),
}))

vi.mock('vue-i18n', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-i18n')>()
  return {
    ...actual,
    useI18n: () => ({ t: (key: string) => key }),
  }
})

describe('DecisionQueryBox', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('does not submit on Enter while commandLoading in command mode', async () => {
    const store = useWorldSessionStore()
    store.interactionState = {
      session: { id: 'sess1', currentSpaceId: 'space1' },
      decision_center: { events: [] },
      focus_map: null,
      context_summary: null,
    } as any
    store.queryMode = 'command'
    store.commandLoading = true

    const submitQuery = vi.spyOn(store, 'submitQuery')

    const wrapper = mount(DecisionQueryBox, {
      global: {
        stubs: { AppIcon: true },
      },
    })

    const input = wrapper.find('input')
    await input.setValue('look')
    await input.trigger('keydown.enter')

    expect(submitQuery).not.toHaveBeenCalled()
  })

  it('does not submit on Enter while commandLoading in AICO mode', async () => {
    const store = useWorldSessionStore()
    store.interactionState = {
      session: { id: 'sess1', currentSpaceId: 'space1' },
      decision_center: { events: [] },
      focus_map: null,
      context_summary: null,
    } as any
    store.queryMode = 'aico'
    store.commandLoading = true

    const submitQuery = vi.spyOn(store, 'submitQuery')

    const wrapper = mount(DecisionQueryBox, {
      global: {
        stubs: { AppIcon: true },
      },
    })

    const input = wrapper.find('input')
    await input.setValue('hello')
    await input.trigger('keydown.enter')

    expect(submitQuery).not.toHaveBeenCalled()
  })

  it('retains input text while sessionActionLoading', async () => {
    const store = useWorldSessionStore()
    store.interactionState = {
      session: { id: 'sess1', currentSpaceId: 'space1' },
      decision_center: { events: [] },
      focus_map: null,
      context_summary: null,
    } as any
    store.queryMode = 'command'
    store.sessionActionLoading = true

    const wrapper = mount(DecisionQueryBox, {
      global: {
        stubs: { AppIcon: true },
      },
    })

    const input = wrapper.find('input')
    await input.setValue('look')
    await input.trigger('keydown.enter')

    expect((input.element as HTMLInputElement).value).toBe('look')
  })

  it('clears input and emits submitted before AICO stream completes', async () => {
    const store = useWorldSessionStore()
    store.interactionState = {
      session: { id: 'sess1', currentSpaceId: 'space1' },
      decision_center: { events: [] },
      focus_map: null,
      context_summary: null,
    } as any
    store.queryMode = 'aico'

    let releaseStream: (() => void) | undefined
    vi.mocked(queryAicoStream).mockImplementationOnce(async () => {
      await new Promise<void>(resolve => {
        releaseStream = resolve
      })
    })

    const wrapper = mount(DecisionQueryBox, {
      global: {
        stubs: { AppIcon: true },
      },
    })

    const input = wrapper.find('input')
    await input.setValue('hello aico')
    const submitPromise = input.trigger('keydown.enter')

    await vi.waitFor(() => {
      expect((input.element as HTMLInputElement).value).toBe('')
    })
    expect(wrapper.emitted('submitted')).toHaveLength(1)
    expect(store.streamInFlight).toBe(true)

    releaseStream?.()
    await submitPromise
    await vi.waitFor(() => expect(store.streamInFlight).toBe(false))
  })
})
