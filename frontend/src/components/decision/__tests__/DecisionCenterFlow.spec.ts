import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DecisionCenterFlow from '../DecisionCenterFlow.vue'
import { useDecisionCenterStore } from '@/stores/decisionCenter'
import { useWorldSessionStore } from '@/stores/worldSession'
import type { WorldInteractionState } from '@/types/world'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

describe('DecisionCenterFlow', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const worldSession = useWorldSessionStore()
    worldSession.loading = false
    worldSession.error = null
    worldSession.interactionState = {
      session: {
        id: 'world_1',
        currentWorldId: null,
        currentSpaceId: '10',
        currentSpaceKey: 'singularity',
        updatedAt: '2026-05-31T00:00:00Z',
      },
      decision_center: {
        focus: { title: 'Focus', summary: 'Summary', severity: 'info' },
        decisionEvents: [],
        activeTask: { id: 'task_1', title: 'Explore', status: 'active' },
        nextBestAction: { id: 'go', label: 'Start', command: 'task start 1' },
        quickQueries: [],
        loading: false,
        error: null,
      },
      focus_map: { mode: 'focus', nodes: [], currentSpaceId: '10' },
      context_summary: {
        currentSpace: { id: '10', name: 'Room', oneLineSummary: 'Hub' },
        pendingDecisionCount: 0,
        nearbyAgents: { total: 0, highlighted: [] },
        suggestedQueries: [],
      },
      quick_queries: [],
    } as unknown as WorldInteractionState
    void useDecisionCenterStore()
  })

  it('always shows active task and next best action regardless of view filter', async () => {
    const wrapper = mount(DecisionCenterFlow, {
      global: {
        stubs: {
          DecisionEventCard: true,
          ActiveTaskCard: { template: '<div class="active-task-stub" />' },
          DecisionQueryBox: true,
          DecisionConversationThread: true,
          AicoThreadToolbar: true,
          ElButton: { template: '<button><slot /></button>' },
        },
      },
    })

    expect(wrapper.find('.active-task-stub').exists()).toBe(true)
    expect(wrapper.find('.next-action').exists()).toBe(true)

    const pendingBtn = wrapper.findAll('button').find(btn => btn.text().includes('worldInteraction.decision.pending'))
    await pendingBtn?.trigger('click')
    expect(wrapper.find('.active-task-stub').exists()).toBe(true)
    expect(wrapper.find('.next-action').exists()).toBe(true)
  })
})
