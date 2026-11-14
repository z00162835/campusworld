import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zh from '@/locales/zh'
import QuestCompanion from '../QuestCompanion.vue'

const render = (busy = false, companionName?: string) => mount(QuestCompanion, {
  props: { busy, companionName },
  global: { plugins: [createI18n({ legacy: false, locale: 'zh', messages: { zh } })] },
})

describe('QuestCompanion', () => {
  it('shows the actual Companion and emits contextual dialogue intents', async () => {
    const wrapper = render(false, 'Maintenance Agent')
    expect(wrapper.text()).toContain('Maintenance Agent')
    await wrapper.findAll('button')[0].trigger('click')
    await wrapper.findAll('button')[1].trigger('click')
    expect(wrapper.emitted('ask')).toEqual([['next_step'], ['explain_basis']])
  })
  it('keeps fallback identity explicit rather than inventing a collaborator', () => {
    expect(render().text()).toContain('AICO')
  })
  it('disables dialogue choices while the session is busy', async () => {
    const wrapper = render(true)
    for (const button of wrapper.findAll('button')) await button.trigger('click')
    expect(wrapper.emitted('ask')).toBeUndefined()
  })
})
