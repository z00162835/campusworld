import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import en from '@/locales/en'
import zh from '@/locales/zh'
import ChoiceConsequence from '../ChoiceConsequence.vue'
import type { DecisionOption } from '@/types/world'

const option: DecisionOption = {
  id: 'inspect', label: 'Inspect', style: 'primary', actionType: 'execute_command', requiresConfirmation: false,
}
const render = (patch: Partial<DecisionOption>, locale = 'en') => mount(ChoiceConsequence, {
  props: { option: { ...option, ...patch } },
  global: { plugins: [createI18n({ legacy: false, locale, messages: { en, zh } })] },
})

describe('ChoiceConsequence', () => {
  it('keeps unknown metadata absent rather than inventing safety claims', () => {
    const wrapper = render({})
    expect(wrapper.text()).toBe('')
  })

  it('shows prediction confidence, uncertainty and source separately', () => {
    const wrapper = render({ consequenceKind: 'predicted', consequenceSummary: 'May reduce vibration',
      consequenceConfidence: 0.72, consequenceProvenanceRefs: ['case:7'] })
    expect(wrapper.text()).toContain('Predicted effect')
    expect(wrapper.text()).toContain('72%')
    expect(wrapper.text()).toContain('not a guarantee')
    expect(wrapper.text()).toContain('case:7')
  })

  it.each([undefined, NaN, -1, 2])('does not fabricate valid confidence from %s', value => {
    expect(render({ consequenceKind: 'predicted', consequenceConfidence: value }).text())
      .toContain('Confidence not provided')
  })

  it('localizes risk, gates, evidence and irreversible impact', () => {
    const wrapper = render({ riskLevel: 'high', gateStatus: 'evidence_required', reversible: false,
      requiredEvidenceRefs: ['observation:3'], affectedEntityRefs: ['device:9'] }, 'zh')
    expect(wrapper.text()).toContain('需要补证')
    expect(wrapper.text()).toContain('不可逆')
    expect(wrapper.text()).not.toContain('high')
    expect(wrapper.text()).toContain('observation:3')
    expect(wrapper.text()).toContain('device:9')
  })

  it('does not present missing prediction provenance as an established basis', () => {
    expect(render({ consequenceKind: 'predicted' }).text()).toContain('Prediction basis not provided')
  })

  it('distinguishes confirmed results from proposed outcomes', () => {
    expect(render({ consequenceKind: 'confirmed', consequenceSummary: 'Rule matched' }).text()).toContain('Confirmed effect')
    expect(render({ consequenceKind: 'proposed', consequenceSummary: 'Will request inspection' }).text()).toContain('Proposed effect')
  })
})
