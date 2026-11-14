import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zh from '@/locales/zh'
import TrackedQuestHud from '../TrackedQuestHud.vue'
import type { TrackedQuestSummary } from '@/types/world'

const quest: TrackedQuestSummary = {
  id: '11', title: 'Restore AHU', state: 'executing', riskLevel: 'high', tracking: 'explicit',
  situation: { id: '31', assertion: 'Vibration high', primarySubjectRef: '42' },
  objectives: [{ id: '21', title: 'Inspect', state: 'in_progress' }], recommendedObjectiveId: '21',
  clues: [{ id: '51', title: 'Reading', assertion: 'Elevated', pinned: false, verificationStatus: 'unverified' }],
}
const render = (foreground = true, busy = false) => mount(TrackedQuestHud, {
  props: { quest, foreground, busy, canFocus: true, canTrack: true, canManageClues: true },
  global: { plugins: [createI18n({ legacy: false, locale: 'zh', messages: { zh } })],
    stubs: { ElButton: { props: ['disabled'], template: '<button :disabled="disabled"><slot /></button>' } } },
})

describe('TrackedQuestHud', () => {
  it('localizes Quest, Objective and clue states while keeping provenance unverified', () => {
    const wrapper = render()
    expect(wrapper.text()).toContain('执行中')
    expect(wrapper.text()).toContain('未验证')
    expect(wrapper.text()).not.toContain('in_progress')
    expect(wrapper.attributes('aria-current')).toBe('true')
    expect(wrapper.get('[role="progressbar"]').attributes('aria-label')).toBeTruthy()
  })
  it('emits focus, pin and tracking intents without changing authoritative state', async () => {
    const wrapper = render()
    await wrapper.get('.quest-token__objective button').trigger('click')
    await wrapper.get('.quest-token__clue button').trigger('click')
    await wrapper.get('.quest-token__actions > button').trigger('click')
    expect(wrapper.emitted('focus')).toEqual([['11', '21']])
    expect(wrapper.emitted('toggleClue')).toEqual([['51']])
    expect(wrapper.emitted('untrack')).toEqual([['11']])
    expect(quest.clues![0].pinned).toBe(false)
  })
  it('does not offer foreground clue pinning for another tracked Quest', () => {
    expect(render(false).find('.quest-token__clue button').exists()).toBe(false)
  })
  it('does not emit mutations when busy but permits read-only map browsing', async () => {
    const wrapper = render(true, true)
    await wrapper.get('.quest-token__objective button').trigger('click')
    expect(wrapper.emitted('focus')).toBeUndefined()
    await wrapper.get('.quest-token__map-refs button').trigger('click')
    expect(wrapper.emitted('locate')).toEqual([['42']])
  })
})
