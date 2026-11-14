import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ActiveTaskCard from '../ActiveTaskCard.vue'
import type { TaskCard } from '@/types/world'

vi.mock('vue-i18n', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-i18n')>()
  return { ...actual, useI18n: () => ({ t: (key: string) => key }) }
})

const baseTask: TaskCard = {
  id: 'task_7',
  title: 'Inspect bearing',
  summary: 'State: claimed',
  status: 'active',
  questId: '11',
  questTitle: 'Restore safe AHU operation',
  progress: 40,
  currentStep: { id: 'step_7', title: 'Start task', shortInstruction: 'Task is claimed.', status: 'active' },
  nextBestAction: {
    id: 'start_7',
    label: 'Start task',
    style: 'primary',
    actionType: 'execute_command',
    requiresConfirmation: false,
  },
  alternativeActions: [],
}

const mountCard = (task: TaskCard) => mount(ActiveTaskCard, {
  props: { task },
  global: {
    plugins: [createPinia()],
    stubs: {
      ElButton: { template: '<button><slot /></button>' },
      ElProgress: true,
    },
  },
})

describe('ActiveTaskCard', () => {
  it('renders semantic mission context and exposes map location', async () => {
    const wrapper = mountCard({
      ...baseTask,
      questContext: {
        state: 'executing',
        riskLevel: 'high',
        situation: {
          id: '9', title: 'AHU anomaly', assertion: 'Bearing vibration exceeds its safe band', subjectRef: '501',
          relatedEntityRefs: ['601'], scopedAtRef: '42',
          triggerKind: 'mixed', confidence: 0.92, severity: 'high',
        },
        goal: { id: '10', title: 'Safe operation', desiredState: 'AHU returns to safe operation' },
        governanceRefs: ['policy:maintenance@3'],
        processRefs: ['process:ahu-bearing@2'],
        qualityRefs: ['quality:vibration@1'],
        caseRefs: [],
      },
    })

    expect(wrapper.text()).toContain('Restore safe AHU operation')
    expect(wrapper.text()).toContain('Bearing vibration exceeds its safe band')
    expect(wrapper.text()).toContain('AHU returns to safe operation')
    expect(wrapper.text()).toContain('Inspect bearing')
    expect(wrapper.classes()).toContain('risk-high')
    expect(wrapper.findAll('.locate-button')).toHaveLength(3)
    await wrapper.findAll('.locate-button')[0].trigger('click')
    expect(wrapper.emitted('locate')).toEqual([['501']])
    const helpButtons = wrapper.findAll('.dialogue-choices button')
    await helpButtons[0].trigger('click')
    await helpButtons[1].trigger('click')
    expect(wrapper.emitted('ask')).toEqual([['next_step'], ['explain_basis']])
  })

  it('keeps legacy objectives usable without inventing quest context', () => {
    const wrapper = mountCard({ ...baseTask, questId: null, questTitle: null, questContext: null })
    expect(wrapper.text()).toContain('Inspect bearing')
    expect(wrapper.text()).toContain('State: claimed')
    expect(wrapper.find('.situation-line').exists()).toBe(false)
    expect(wrapper.find('.el-progress').exists()).toBe(false)
  })
})
