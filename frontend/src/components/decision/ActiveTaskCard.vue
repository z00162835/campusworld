<template>
  <article
    class="task-card"
    :class="[`risk-${task.questContext?.riskLevel || 'normal'}`, { 'is-map-related': mapRelated }]"
  >
    <div class="mission-kicker">
      <span>{{ t('worldInteraction.decision.trackedQuest') }}</span>
      <span v-if="task.questContext" class="risk-label">
        {{ t('worldInteraction.decision.risk', { level: t(`worldInteraction.decision.riskLevel.${task.questContext.riskLevel}`) }) }}
      </span>
    </div>
    <div class="task-header">
      <div class="task-title-row">
        <h3>{{ task.questTitle || task.title }}</h3>
        <span class="task-status-pill">{{ task.questContext?.state || task.status }}</span>
      </div>
      <span v-if="task.questContext && task.progress !== null" class="task-progress-label">
        {{ t('worldInteraction.decision.questProgress', { value: task.progress }) }}
      </span>
    </div>
    <p v-if="task.questContext?.situation" class="situation-line">
      <span>{{ t('worldInteraction.decision.situation') }}</span>
      {{ task.questContext.situation.assertion || task.questContext.situation.title }}
    </p>
    <div v-if="mapRefs.length" class="mission-map-refs">
      <el-button
        v-for="ref in mapRefs"
        :key="ref.id"
        class="locate-button"
        size="small"
        text
        @click="$emit('locate', ref.id)"
      >
        {{ t('worldInteraction.quest.locateRef', { kind: t(`worldInteraction.quest.mapRefKind.${ref.kind}`), id: ref.id }) }}
      </el-button>
    </div>
    <p v-if="task.questContext?.goal" class="goal-line">
      <span>{{ t('worldInteraction.decision.goal') }}</span>
      {{ task.questContext.goal.desiredState || task.questContext.goal.title }}
    </p>
    <p v-if="!task.questContext">{{ task.summary }}</p>
    <el-progress v-if="task.questContext && task.progress !== null" :percentage="task.progress" :show-text="false" />
    <div v-if="task.questContext" class="provenance-row">
      <span class="provenance-chip">{{ triggerLabel }}</span>
      <span v-if="task.questContext.situation?.confidence != null" class="provenance-chip">
        {{ t('worldInteraction.decision.confidence', { value: confidencePercent }) }}
      </span>
      <span v-if="governanceCount" class="provenance-chip">
        {{ t('worldInteraction.decision.governanceCount', { count: governanceCount }) }}
      </span>
    </div>
    <div class="step objective-step">
      <span>{{ t('worldInteraction.decision.currentObjective') }}</span>
      <small v-if="task.questTitle">{{ task.title }}</small>
      <strong>{{ task.currentStep.title }}</strong>
      <p>{{ task.currentStep.shortInstruction }}</p>
    </div>
    <QuestCompanion
      v-if="task.questId"
      :companion-name="task.questContext?.companion?.name"
      :busy="worldSession.sessionActionBusy"
      @ask="$emit('ask', $event)"
    />
    <div class="mission-actions">
      <el-button
        type="primary"
        size="small"
        :disabled="worldSession.sessionActionBusy"
        aria-describedby="mission-next-action-consequence"
        @click="executeNextAction"
      >
        {{ optionLabel(task.nextBestAction) }}
      </el-button>
      <ChoiceConsequence
        id="mission-next-action-consequence"
        :option="task.nextBestAction"
      />
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessageBox } from 'element-plus'
import { useWorldSessionStore } from '@/stores/worldSession'
import type { DecisionOption, TaskCard } from '@/types/world'
import ChoiceConsequence from './ChoiceConsequence.vue'
import QuestCompanion from './QuestCompanion.vue'

const props = defineProps<{
  task: TaskCard
  mapRelated?: boolean
}>()

const emit = defineEmits<{
  execute: [optionId: string]
  locate: [entityId: string]
  ask: [intent: 'next_step' | 'explain_basis']
}>()

const { t } = useI18n()
const worldSession = useWorldSessionStore()
const optionLabel = (option: DecisionOption) =>
  option.labelKey ? t(option.labelKey, option.labelParams || {}) : option.label
const executeNextAction = async () => {
  if (worldSession.sessionActionBusy) return
  const taskId = props.task.id
  const option = props.task.nextBestAction
  if (option.requiresConfirmation) {
    try {
      await ElMessageBox.confirm(
        option.consequenceSummaryKey ? t(option.consequenceSummaryKey)
          : option.consequenceSummary || t('worldInteraction.decision.confirmAction'),
        t('worldInteraction.decision.confirmTitle'),
        { confirmButtonText: t('worldInteraction.decision.confirm'), cancelButtonText: t('worldInteraction.decision.cancel'), type: 'warning' },
      )
    } catch {
      return
    }
  }
  if (worldSession.sessionActionBusy || props.task.id !== taskId || props.task.nextBestAction !== option) return
  emit('execute', option.id)
}
const confidencePercent = computed(() => Math.round((props.task.questContext?.situation?.confidence || 0) * 100))
const mapRefs = computed(() => {
  const situation = props.task.questContext?.situation
  if (!situation) return []
  const refs = [
    ...(situation.subjectRef ? [{ id: situation.subjectRef, kind: 'primary' }] : []),
    ...(situation.relatedEntityRefs || []).map(id => ({ id, kind: 'related' })),
    ...(situation.scopedAtRef ? [{ id: situation.scopedAtRef, kind: 'scope' }] : []),
  ]
  return refs.filter((ref, index) => refs.findIndex(item => item.id === ref.id) === index)
})
const governanceCount = computed(() => {
  const context = props.task.questContext
  return context ? context.governanceRefs.length + context.processRefs.length + context.qualityRefs.length : 0
})
const triggerLabel = computed(() => {
  const kind = props.task.questContext?.situation?.triggerKind || 'manual'
  return t(`worldInteraction.decision.trigger.${kind}`)
})
</script>

<style scoped>
.task-card {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--decision-card-bg);
  padding: var(--spacing-lg);
  border-left: 3px solid var(--color-primary);
}

.task-card.risk-high,
.task-card.risk-critical {
  border-left-color: var(--color-danger);
}

.task-card.is-map-related {
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.45);
}

.mission-kicker {
  display: flex;
  justify-content: space-between;
  color: var(--color-primary);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: var(--spacing-sm);
}

.risk-label {
  color: var(--text-tertiary);
}

.task-header {
  display: flex;
  justify-content: space-between;
  gap: var(--spacing-md);
  align-items: flex-start;
}

.task-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--spacing-sm);
}

h3 {
  margin: 0;
  font-size: var(--font-size-base);
}

.task-status-pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-md);
  background: rgba(64, 158, 255, 0.12);
  color: var(--color-primary);
  font-size: var(--font-size-xs);
  text-transform: uppercase;
}

.task-progress-label {
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  flex-shrink: 0;
}

p {
  margin: var(--spacing-sm) 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

.situation-line,
.goal-line {
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
}

.situation-line span,
.goal-line span {
  display: block;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  text-transform: uppercase;
}

.locate-button {
  display: block;
  margin-top: var(--spacing-xs);
  padding-left: 0;
}

.mission-map-refs {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.provenance-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
  margin-top: var(--spacing-sm);
}

.provenance-chip {
  padding: 2px 8px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}

.step {
  margin: var(--spacing-md) 0;
}

.step span {
  display: block;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  text-transform: uppercase;
  margin-bottom: var(--spacing-xs);
}

.objective-step small {
  display: block;
  margin-bottom: var(--spacing-xs);
  color: var(--text-secondary);
}

.mission-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.mission-action-consequence {
  margin: 5px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

</style>
