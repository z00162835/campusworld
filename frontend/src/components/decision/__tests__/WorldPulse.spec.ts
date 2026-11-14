import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zh from '@/locales/zh'
import WorldPulse from '../WorldPulse.vue'
import type { WorldPulseItem } from '@/types/world'

const item: WorldPulseItem = { id: '1', situationId: '31', severity: 'high', assertion: 'Bearing anomaly', attention: 'new' }
const render = (patch: Partial<WorldPulseItem> = {}, busy = false) => mount(WorldPulse, {
  props: { items: [{ ...item, ...patch }], busy },
  global: {
    plugins: [createI18n({ legacy: false, locale: 'zh', messages: { zh } })],
    stubs: { ElButton: { props: ['disabled'], template: '<button :disabled="disabled"><slot /></button>' } },
  },
})

describe('WorldPulse', () => {
  it('emits account attention intents without changing the authoritative item', async () => {
    const wrapper = render()
    await wrapper.findAll('button')[0].trigger('click')
    expect(wrapper.emitted('attention')).toEqual([['31', 'seen']])
    expect(wrapper.props('items')[0].attention).toBe('new')
    expect(wrapper.text()).toContain('Bearing anomaly')
    expect(wrapper.text()).not.toContain('high')
  })

  it('keeps snooze and UI-dismiss separate from business resolution', async () => {
    const wrapper = render()
    await wrapper.findAll('button')[1].trigger('click')
    await wrapper.findAll('button')[2].trigger('click')
    expect(wrapper.emitted('snooze')).toEqual([['31']])
    expect(wrapper.emitted('attention')).toEqual([['31', 'ui_dismissed']])
  })

  it('restores snoozed attention without resolving a Situation', async () => {
    const wrapper = render({ attention: 'snoozed' })
    await wrapper.findAll('button')[0].trigger('click')
    expect(wrapper.emitted('attention')).toEqual([['31', 'reset']])
  })

  it('disables all actions while a server mutation is pending', async () => {
    const wrapper = render({}, true)
    for (const button of wrapper.findAll('button')) {
      expect(button.attributes()).toHaveProperty('disabled')
      await button.trigger('click')
    }
    expect(wrapper.emitted('attention')).toBeUndefined()
    expect(wrapper.emitted('snooze')).toBeUndefined()
  })

  it('shows human escalation with its reason and correlation without rewriting the Situation', () => {
    const wrapper = render({ escalation: { reasonCode: 'missing_evidence', objectiveId: '21', correlationId: 'corr-7' } })
    expect(wrapper.text()).toContain('需要人工介入')
    expect(wrapper.text()).toContain('所需证据缺失或尚未验证')
    expect(wrapper.text()).toContain('corr-7')
    expect(wrapper.props('items')[0].assertion).toBe(item.assertion)
  })
})
