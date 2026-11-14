import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zh from '@/locales/zh'
import QuestJournal from '../QuestJournal.vue'
import type { QuestInteractionStatePayload } from '@/types/world'

const journal: NonNullable<QuestInteractionStatePayload['questJournal']> = {
  nodes: [
    { id: '11', type: 'quest', label: 'Restore AHU' },
    { id: '21', type: 'task', label: 'Inspect' },
    { id: '42', type: 'room', label: 'Plant room' },
    { id: '51', type: 'observation', label: 'Vibration', verificationStatus: 'unverified' },
  ],
  edges: [
    { id: 'e1', type: 'HAS_OBJECTIVE', sourceId: '11', targetId: '21' },
    { id: 'e2', type: 'SCOPED_AT', sourceId: '21', targetId: '42' },
    { id: 'hidden', type: 'SUPPORTED_BY', sourceId: '51', targetId: 'secret' },
  ],
  unresolvedRefs: [{ ref: 'policy:2', expectedType: 'policy', reason: 'not_materialized' }],
}
const render = () => mount(QuestJournal, {
  props: { journal, locatableEntityIds: ['42'], selectedEntityId: null },
  global: { plugins: [createI18n({ legacy: false, locale: 'zh', messages: { zh } })] },
})

describe('QuestJournal', () => {
  it('shows localized visible relationships on explicit read-only node selection', async () => {
    const wrapper = render()
    await wrapper.findAll('.quest-journal__node button')[1].trigger('click')
    expect(wrapper.get('.quest-journal__selection').text()).toContain('Restore AHU → 包含行动目标 → Inspect')
    expect(wrapper.get('.quest-journal__selection').text()).toContain('Inspect → 作用于 → Plant room')
    expect(wrapper.findAll('.quest-journal__node button')[1].attributes('aria-pressed')).toBe('true')
    expect(wrapper.emitted('locate')).toBeUndefined()
  })

  it('emits map location only for explicitly supplied entity references', async () => {
    const wrapper = render()
    await wrapper.findAll('.quest-journal__node button')[2].trigger('click')
    await wrapper.get('.quest-journal__selection button').trigger('click')
    expect(wrapper.emitted('locate')).toEqual([['42']])
    await wrapper.findAll('.quest-journal__node button')[0].trigger('click')
    expect(wrapper.findAll('.quest-journal__selection button')).toHaveLength(1)
  })

  it('does not expose connections to nodes missing from the authorized projection', async () => {
    const wrapper = render()
    await wrapper.findAll('.quest-journal__node button')[3].trigger('click')
    expect(wrapper.text()).toContain('未验证')
    expect(wrapper.get('.quest-journal__selection').text()).toContain('当前日志视图中没有可见关联')
    expect(wrapper.text()).not.toContain('secret')
    expect(wrapper.find('.quest-journal__unresolved button').exists()).toBe(false)
  })

  it('reflects map selection without changing the graph or durable focus', async () => {
    const wrapper = render()
    await wrapper.setProps({ selectedEntityId: '42' })
    expect(wrapper.findAll('.quest-journal__node')[2].classes()).toContain('quest-journal__node--map-related')
    expect(wrapper.findAll('.quest-journal__node')[2].text()).toContain('地图当前选中')
    expect(wrapper.emitted('locate')).toBeUndefined()
    expect(wrapper.props('journal')).toEqual(journal)
  })

  it('clears stale local selection when the foreground journal changes', async () => {
    const wrapper = render()
    await wrapper.findAll('.quest-journal__node button')[0].trigger('click')
    await wrapper.setProps({ journal: { nodes: [{ id: '12', type: 'quest', label: 'New Quest' }], edges: [], unresolvedRefs: [] } })
    expect(wrapper.find('.quest-journal__selection').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Restore AHU')
  })

  it('clears journal selection without emitting a map or business mutation', async () => {
    const wrapper = render()
    await wrapper.findAll('.quest-journal__node button')[0].trigger('click')
    await wrapper.findAll('.quest-journal__selection button').at(-1)!.trigger('click')
    expect(wrapper.find('.quest-journal__selection').exists()).toBe(false)
    expect(wrapper.emitted('locate')).toBeUndefined()
  })

  it('does not locate a semantic Quest node even if a reference list includes it', async () => {
    const wrapper = render()
    await wrapper.setProps({ locatableEntityIds: ['11', '42'] })
    await wrapper.findAll('.quest-journal__node button')[0].trigger('click')
    expect(wrapper.findAll('.quest-journal__selection button')).toHaveLength(1)
    expect(wrapper.emitted('locate')).toBeUndefined()
  })
})
