<template>
  <div class="choice-consequence">
    <p v-if="summary">
      <strong>{{ t(`worldInteraction.decision.consequenceKind.${option.consequenceKind || 'proposed'}`) }}</strong>
      {{ summary }}
    </p>
    <p v-if="option.consequenceKind === 'predicted'">
      {{ confidence === null ? t('worldInteraction.decision.choice.unknownConfidence') : t('worldInteraction.decision.confidence', { value: confidence }) }}
      · {{ t('worldInteraction.decision.choice.uncertain') }}
    </p>
    <p v-if="option.consequenceKind === 'predicted' && !option.consequenceProvenanceRefs?.length">
      {{ t('worldInteraction.decision.choice.unknownSources') }}
    </p>
    <p v-if="option.gateReasonCode">{{ gateReason }}</p>
    <dl>
      <template v-if="option.riskLevel">
        <dt>{{ t('worldInteraction.decision.choice.risk') }}</dt>
        <dd>{{ t(`worldInteraction.decision.riskLevel.${option.riskLevel}`) }}</dd>
      </template>
      <template v-if="option.gateStatus">
        <dt>{{ t('worldInteraction.decision.choice.gate') }}</dt>
        <dd>{{ t(`worldInteraction.decision.choice.gates.${option.gateStatus}`) }}</dd>
      </template>
      <template v-if="typeof option.reversible === 'boolean'">
        <dt>{{ t('worldInteraction.decision.choice.reversibility') }}</dt>
        <dd>{{ t(`worldInteraction.decision.choice.${option.reversible ? 'reversible' : 'irreversible'}`) }}</dd>
      </template>
      <template v-for="group in referenceGroups" :key="group.key">
        <dt>{{ t(`worldInteraction.decision.choice.${group.key}`) }}</dt>
        <dd>{{ group.refs.join(', ') }}</dd>
      </template>
    </dl>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { DecisionOption } from '@/types/world'

const props = defineProps<{ option: DecisionOption }>()
const { t, te } = useI18n()
const gateReason = computed(() => {
  const code = props.option.gateReasonCode || ''
  const key = `worldInteraction.quest.executionReason.${code}`
  return te(key) ? t(key) : t('worldInteraction.quest.executionUnknownReason', { code })
})
const summary = computed(() => props.option.consequenceSummaryKey
  ? t(props.option.consequenceSummaryKey) : props.option.consequenceSummary)
const confidence = computed(() => {
  const value = props.option.consequenceConfidence
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1
    ? Math.round(value * 100) : null
})
const referenceGroups = computed(() => [
  { key: 'sources', refs: props.option.consequenceProvenanceRefs || [] },
  { key: 'evidence', refs: props.option.requiredEvidenceRefs || [] },
  { key: 'affected', refs: props.option.affectedEntityRefs || [] },
].filter(group => group.refs.length > 0))
</script>

<style scoped>
.choice-consequence { color: var(--text-secondary); font-size: var(--font-size-xs); line-height: 1.5; overflow-wrap: anywhere; max-width: 36rem; }
p { margin: 4px 0; }
dl { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 4px 12px; margin: 4px 0; }
dt { font-weight: var(--font-weight-semibold); }
dd { margin: 0; }
</style>
