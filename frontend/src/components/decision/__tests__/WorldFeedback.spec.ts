import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import en from '@/locales/en'
import zh from '@/locales/zh'
import WorldFeedback from '../WorldFeedback.vue'
import type { WorldFeedbackItem } from '@/types/world'

const event: WorldFeedbackItem = {
  id: 'transition:21:1', questId: '11', objectiveId: '21', actorKind: 'agent', actorId: '99',
  status: 'failed', summary: 'Inspect bearing', objectiveState: 'failed',
  correlationId: 'corr-123', occurredAt: '2026-11-14T10:00:00Z',
}
const render = (items: WorldFeedbackItem[], locale = 'en') => mount(WorldFeedback, {
  props: { items },
  global: { plugins: [createI18n({ legacy: false, locale, messages: { en, zh } })] },
})

describe('WorldFeedback', () => {
  it('shows the recorded executor, outcome, timestamp and trace references', () => {
    const wrapper = render([event])
    expect(wrapper.text()).toContain('Agent · #99')
    expect(wrapper.text()).toContain('Inspect bearing → failed')
    expect(wrapper.get('time').attributes('datetime')).toBe(event.occurredAt)
    expect(wrapper.get('details').text()).toContain('corr-123')
    expect(wrapper.get('details').text()).toContain('11')
    expect(wrapper.get('details').text()).toContain('21')
    expect(wrapper.get('[role="log"]').attributes('aria-live')).toBe('polite')
  })

  it('does not attribute other human actions to the current user', () => {
    const wrapper = render([{ ...event, actorKind: 'human', actorId: '5' }])
    expect(wrapper.text()).toContain('Human · #5')
    expect(wrapper.text()).not.toContain('You')
  })

  it('does not invent a time, executor ID or correlation when data is missing', () => {
    const wrapper = render([{ ...event, occurredAt: 'invalid', actorKind: 'system', actorId: null, correlationId: '' }])
    expect(wrapper.find('time').exists()).toBe(false)
    expect(wrapper.text()).toContain('Time not available')
    expect(wrapper.text()).toContain('Not provided')
    expect(wrapper.text()).not.toContain('#')
    expect(wrapper.text()).not.toContain('Invalid Date')
  })

  it('localizes status and audit labels in Chinese', () => {
    const wrapper = render([{ ...event, actorKind: 'human', objectiveState: 'pending_review', status: 'blocked' }], 'zh')
    expect(wrapper.text()).toContain('人工')
    expect(wrapper.text()).toContain('追溯此行动')
    expect(wrapper.text()).toContain('关联追踪标识')
    expect(wrapper.text()).not.toContain('pending_review')
  })

  it('keeps unknown future Objective states without declaring them completed', () => {
    expect(render([{ ...event, objectiveState: 'waiting_external' }]).text()).toContain('waiting_external')
  })

  it('does not manufacture feedback for an empty history', () => {
    expect(render([]).find('section').exists()).toBe(false)
  })

  it('does not present automatic command success as Quest acceptance', () => {
    const wrapper = render([{ ...event, status: 'succeeded', objectiveState: undefined,
      reasonCode: 'command_completed_verification_pending' }], 'zh')
    expect(wrapper.text()).toContain('任务线是否验收仍需验证')
  })
})
