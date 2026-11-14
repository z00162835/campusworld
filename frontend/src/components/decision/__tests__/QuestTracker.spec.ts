import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import QuestTracker from '../QuestTracker.vue'
import { useWorldSessionStore } from '@/stores/worldSession'
import type { WorldInteractionState } from '@/types/world'

vi.mock('vue-i18n', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-i18n')>()
  return { ...actual, useI18n: () => ({ t: (key: string) => key }) }
})

describe('QuestTracker', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const store = useWorldSessionStore()
    store.interactionState = {
      session: { id: 'world_1', currentWorldId: 'hicampus', currentSpaceId: '1', updatedAt: 'now' },
      decision_center: {
        focus: null,
        decisionEvents: [],
        activeTask: null,
        nextBestAction: null,
        quickQueries: [],
        loading: false,
        error: null,
      },
      focus_map: {
        mode: 'focus', nodes: [], edges: [], agentPresences: [], highlightedPath: [],
        currentSpaceId: '1', selectedEntityId: null, loading: false,
      },
      context_summary: {
        currentSpace: { id: '1', name: 'Room', oneLineSummary: 'Room' },
        nearbyAgents: { total: 0, highlighted: [] },
        pendingDecisionCount: 0,
        suggestedQueries: [],
      },
      quest_interaction: {
        contractVersion: 'quest-interaction.v1',
        capabilities: ['multi_quest_tracking', 'durable_focus', 'observation_clues', 'quest_graph', 'situation_attention'],
        projectionRevision: '4',
        lastEventId: '19',
        foregroundQuestId: '11',
        worldPulse: [{ id: '31', situationId: '31', severity: 'high', assertion: 'AHU vibration is high', attention: 'new' }],
        trackedQuests: [
          {
            id: '11', title: 'Restore AHU', state: 'executing', riskLevel: 'high', tracking: 'explicit',
            focusedObjectiveId: '21', situation: { id: '31', assertion: 'AHU vibration is high' },
            goal: { id: '41', desiredState: 'AHU is safe' },
            objectives: [
              { id: '21', title: 'Inspect bearing', state: 'in_progress' },
              { id: '23', title: 'Check fan belt', state: 'open' },
            ],
            clues: [{ id: '51', title: 'Bearing vibration', assertion: 'Vibration exceeded baseline', verificationStatus: 'unverified', pinned: false }],
            progress: { total_objectives: 1, terminal_objectives: 0, completed_objectives: 0, percent: 0, success_percent: 0 },
          },
          {
            id: '12', title: 'Review access', state: 'draft', riskLevel: 'normal', tracking: 'explicit',
            recommendedObjectiveId: '22', objectives: [{ id: '22', title: 'Review log', state: 'open' }],
          },
        ],
        questJournal: {
          nodes: [
            { id: '11', type: 'quest', label: 'Restore AHU' },
            { id: '51', type: 'observation', label: 'Bearing vibration' },
          ],
          edges: [],
          unresolvedRefs: [{ ref: 'policy:safety@2', expectedType: 'policy', reason: 'not_materialized' }],
        },
      },
      quick_queries: [],
    } as WorldInteractionState
  })

  it('renders multiple explicit Quests and sends focus without changing Objective state locally', async () => {
    const store = useWorldSessionStore()
    const execute = vi.spyOn(store, 'executeQuestInteractionAction').mockResolvedValue(undefined)
    const wrapper = mount(QuestTracker, {
      global: { stubs: { ElButton: { template: '<button @click="$emit(\'click\')"><slot /></button>' } } },
    })

    expect(wrapper.text()).toContain('Restore AHU')
    expect(wrapper.text()).toContain('Review access')
    expect(wrapper.findAll('.quest-token')).toHaveLength(2)
    const focus = wrapper.findAll('.quest-token')[1].findAll('button')[0]
    await focus.trigger('click')
    expect(execute).toHaveBeenCalledWith({ action: 'focus_objective', questId: '12', objectiveId: '22' })
    expect(store.questInteraction?.trackedQuests[1].objectives[0].state).toBe('open')
  })

  it('shows unresolved semantic refs as journal leaves', async () => {
    const wrapper = mount(QuestTracker, {
      global: { stubs: { ElButton: { template: '<button><slot /></button>' } } },
    })
    await wrapper.find('summary').trigger('click')
    expect(wrapper.text()).toContain('policy:safety@2')
    expect(wrapper.text()).toContain('worldInteraction.quest.unresolved.not_materialized')
  })

  it('pins a materialized observation for the foreground Quest', async () => {
    const store = useWorldSessionStore()
    const execute = vi.spyOn(store, 'executeQuestInteractionAction').mockResolvedValue(undefined)
    const wrapper = mount(QuestTracker, {
      global: { stubs: { ElButton: { template: '<button @click="$emit(\'click\')"><slot /></button>' } } },
    })

    const clueButton = wrapper.findAll('.quest-token__clue button')[0]
    expect(clueButton.text()).toBe('worldInteraction.quest.pinClue')
    await clueButton.trigger('click')
    expect(execute).toHaveBeenCalledWith({ action: 'pin_clue', questId: '11', clueNodeId: '51' })
  })

  it('persists Pulse attention without treating dismissal as Situation resolution', async () => {
    const store = useWorldSessionStore()
    const execute = vi.spyOn(store, 'executeQuestInteractionAction').mockResolvedValue(undefined)
    const wrapper = mount(QuestTracker, {
      global: { stubs: { ElButton: { template: '<button @click="$emit(\'click\')"><slot /></button>' } } },
    })

    expect(wrapper.text()).toContain('worldInteraction.quest.worldPulse.title')
    await wrapper.find('.world-pulse__actions button').trigger('click')
    expect(execute).toHaveBeenCalledWith({ action: 'situation_attention', situationId: '31', attention: 'seen' })
    expect(store.questInteraction?.worldPulse?.[0].attention).toBe('new')
  })

  it('allows changing Objective focus within the currently focused Quest', async () => {
    const store = useWorldSessionStore()
    const execute = vi.spyOn(store, 'executeQuestInteractionAction').mockResolvedValue(undefined)
    const wrapper = mount(QuestTracker, {
      global: { stubs: { ElButton: { template: '<button @click="$emit(\'click\')"><slot /></button>' } } },
    })

    const objectiveButton = wrapper.findAll('.quest-token')[0].find('.quest-token__objective button')
    await objectiveButton.trigger('click')
    expect(execute).toHaveBeenCalledWith({ action: 'focus_objective', questId: '11', objectiveId: '23' })
  })

  it('emits map navigation for related and scoped entities', async () => {
    const store = useWorldSessionStore()
    store.questInteraction!.trackedQuests[0].situation = {
      id: '31', assertion: 'AHU vibration is high', primarySubjectRef: '501',
      relatedEntityRefs: ['601'], scopedAtRef: '42',
    }
    const wrapper = mount(QuestTracker, {
      global: { stubs: { ElButton: { template: '<button><slot /></button>' } } },
    })

    const links = wrapper.findAll('.quest-token__map-refs button')
    expect(links).toHaveLength(3)
    await links[1].trigger('click')
    expect(wrapper.emitted('locate')?.[0]).toEqual(['601'])
  })

  it('hides writes and Journal when their capabilities are absent', () => {
    const store = useWorldSessionStore()
    store.questInteraction!.capabilities = []
    store.decisionCenter!.activeTask = {
      id: 'task_3', title: 'Discovered', summary: 'Discovered Quest', status: 'active', progress: 0,
      questId: '99', questTitle: 'Hidden controls', blockers: [],
      currentStep: { id: 'step_3', title: 'Review', shortInstruction: '', status: 'active' },
      nextBestAction: {
        id: 'show', label: 'Show', style: 'primary', actionType: 'execute_command',
        requiresConfirmation: false,
      },
      alternativeActions: [],
    }
    const wrapper = mount(QuestTracker, {
      global: { stubs: { ElButton: { template: '<button><slot /></button>' } } },
    })

    expect(wrapper.find('.quest-tracker__callout').exists()).toBe(false)
    expect(wrapper.findAll('.quest-token__actions button')).toHaveLength(0)
    expect(wrapper.find('.quest-journal').exists()).toBe(false)
  })
})
