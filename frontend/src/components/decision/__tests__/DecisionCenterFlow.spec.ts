import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DecisionCenterFlow from '../DecisionCenterFlow.vue'
import { useDecisionCenterStore } from '@/stores/decisionCenter'
import { useWorldSessionStore } from '@/stores/worldSession'
import type { WorldInteractionState } from '@/types/world'

vi.mock('vue-i18n', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-i18n')>()
  return {
    ...actual,
    useI18n: () => ({
      t: (key: string) => key,
    }),
  }
})

describe('DecisionCenterFlow', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const worldSession = useWorldSessionStore()
    worldSession.loading = false
    worldSession.error = null
    worldSession.queryMode = 'aico'
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
        decisionEvents: [
          {
            id: 'evt_1',
            title: 'Event',
            summary: 'Pending',
            priority: 'important',
            impact: 'High',
            recommendation: 'Act',
            options: [{ id: 'opt_1', label: 'Go', style: 'primary', command: 'x' }],
          },
        ],
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

  const mountOptions = {
    global: {
      stubs: {
        DecisionEventCard: true,
        ActiveTaskCard: { template: '<div class="active-task-stub" />' },
        DecisionQueryBox: { template: '<div class="query-box-stub" />' },
        DecisionConversationThread: true,
        AicoThreadToolbar: true,
        ElButton: { template: '<button><slot /></button>' },
        ElIcon: { template: '<span><slot /></span>' },
      },
    },
  }

  async function cycleFold(wrapper: ReturnType<typeof mount>) {
    await wrapper.find('.fold-hinge').trigger('keydown.enter')
  }

  it('defaults to collapsed task zone so hinge sits above interaction header', () => {
    const wrapper = mount(DecisionCenterFlow, mountOptions)
    expect(wrapper.find('.task-zone').classes()).toContain('collapsed')
    expect(wrapper.find('.zone-divider-hint').text()).toContain('worldInteraction.decision.taskZoneCollapsedHint')
  })

  it('enters split mode on first expand and keeps conversation visible', async () => {
    const wrapper = mount(DecisionCenterFlow, mountOptions)

    await cycleFold(wrapper)
    expect(wrapper.find('.decision-fold').classes()).toContain('mode-split')
    expect(wrapper.find('.active-task-stub').exists()).toBe(true)
    expect(wrapper.find('.conversation-zone').attributes('style') ?? '').not.toMatch(/display:\s*none/)
  })

  it('maximizes task zone on second expand and hides conversation content', async () => {
    const wrapper = mount(DecisionCenterFlow, mountOptions)

    await cycleFold(wrapper)
    await cycleFold(wrapper)
    expect(wrapper.find('.decision-fold').classes()).toContain('task-expanded')
    expect(wrapper.find('.conversation-zone').attributes('style')).toMatch(/display:\s*none/)
    expect(wrapper.find('.query-box-stub').exists()).toBe(true)
    expect(wrapper.find('.active-task-stub').exists()).toBe(true)
  })

  it('returns to collapsed mode after third hinge cycle', async () => {
    const wrapper = mount(DecisionCenterFlow, mountOptions)

    await cycleFold(wrapper)
    await cycleFold(wrapper)
    await cycleFold(wrapper)
    expect(wrapper.find('.task-zone').classes()).toContain('collapsed')
    expect(wrapper.find('.conversation-zone').attributes('style') ?? '').not.toMatch(/display:\s*none/)
  })

  it('renders zone chrome and divider', () => {
    const wrapper = mount(DecisionCenterFlow, mountOptions)

    expect(wrapper.find('.task-zone-header').exists()).toBe(true)
    expect(wrapper.find('.conversation-zone-header').exists()).toBe(true)
    expect(wrapper.find('.zone-divider').exists()).toBe(true)
    expect(wrapper.find('.zone-badge').exists()).toBe(true)
  })

  it('collapses task zone on query submit when task zone was maximized', async () => {
    const wrapper = mount(DecisionCenterFlow, {
      global: {
        stubs: {
          ...mountOptions.global.stubs,
          DecisionQueryBox: {
            template: '<button class="query-submit-stub" @click="$emit(\'submitted\')" />',
          },
        },
      },
    })

    await cycleFold(wrapper)
    await cycleFold(wrapper)
    expect(wrapper.find('.decision-fold').classes()).toContain('task-expanded')

    await wrapper.find('.query-submit-stub').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.task-zone').classes()).toContain('collapsed')
    expect(wrapper.find('.conversation-zone').attributes('style') ?? '').not.toMatch(/display:\s*none/)
  })
})
