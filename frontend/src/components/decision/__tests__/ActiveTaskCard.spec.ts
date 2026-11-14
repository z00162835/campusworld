import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ActiveTaskCard from '../ActiveTaskCard.vue'
import type { TaskCard } from '@/types/world'
import { ElMessageBox } from 'element-plus'

// The installed library declares an input/action intersection; confirm resolves to an action.
const confirmed = 'confirm' as Awaited<ReturnType<typeof ElMessageBox.confirm>>

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
  it('asks for confirmation before emitting an irreversible action', async () => {
    const confirm = vi.spyOn(ElMessageBox, 'confirm').mockResolvedValueOnce(confirmed)
    const wrapper = mountCard({ ...baseTask, nextBestAction: {
      ...baseTask.nextBestAction, requiresConfirmation: true, consequenceSummary: 'Only this Objective completes',
    } })
    await wrapper.get('.mission-actions button').trigger('click')
    expect(confirm).toHaveBeenCalledWith('Only this Objective completes', expect.any(String), expect.any(Object))
    expect(wrapper.emitted('execute')).toEqual([['start_7']])
    confirm.mockRestore()
  })

  it('does not execute a cancelled confirmation', async () => {
    const confirm = vi.spyOn(ElMessageBox, 'confirm').mockRejectedValueOnce('cancel')
    const wrapper = mountCard({ ...baseTask, nextBestAction: { ...baseTask.nextBestAction, requiresConfirmation: true } })
    await wrapper.get('.mission-actions button').trigger('click')
    expect(wrapper.emitted('execute')).toBeUndefined()
    confirm.mockRestore()
  })

  it('does not execute an action replaced while confirmation is open', async () => {
    let resolveConfirmation!: (value: Awaited<ReturnType<typeof ElMessageBox.confirm>>) => void
    const confirm = vi.spyOn(ElMessageBox, 'confirm').mockImplementationOnce(() => new Promise(resolve => { resolveConfirmation = resolve }))
    const wrapper = mountCard({ ...baseTask, nextBestAction: { ...baseTask.nextBestAction, requiresConfirmation: true } })
    await wrapper.get('.mission-actions button').trigger('click')
    await wrapper.setProps({ task: { ...baseTask, id: 'task_8' } })
    resolveConfirmation(confirmed)
    await Promise.resolve()
    expect(wrapper.emitted('execute')).toBeUndefined()
    confirm.mockRestore()
  })
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
