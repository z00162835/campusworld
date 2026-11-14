<template>
  <section v-if="items.length" class="world-feedback" :aria-label="t('worldInteraction.quest.worldFeedback.title')">
    <h4>{{ t('worldInteraction.quest.worldFeedback.title') }}</h4>
    <ol role="log" aria-live="polite" aria-relevant="additions text">
      <li v-for="item in items" :key="item.id">
        <div class="feedback-summary">
          <span>{{ t(`worldInteraction.quest.worldFeedback.actor.${item.actorKind}`) }}<template v-if="item.actorId"> · #{{ item.actorId }}</template></span>
          <strong>{{ item.summary }}<template v-if="item.objectiveState"> → {{ stateLabel(item.objectiveState) }}</template></strong>
          <span>{{ t(`worldInteraction.quest.worldFeedback.status.${item.status}`) }}</span>
        </div>
        <p v-if="item.reasonCode">{{ reasonLabel(item.reasonCode) }}</p>
        <time v-if="validTime(item.occurredAt)" :datetime="item.occurredAt">{{ formatTime(item.occurredAt) }}</time>
        <span v-else>{{ t('worldInteraction.quest.worldFeedback.unknownTime') }}</span>
        <details>
          <summary>{{ t('worldInteraction.quest.worldFeedback.auditDetails') }}</summary>
          <dl>
            <dt>{{ t('worldInteraction.quest.worldFeedback.questRef') }}</dt><dd>{{ item.questId }}</dd>
            <template v-if="item.objectiveId">
              <dt>{{ t('worldInteraction.quest.worldFeedback.objectiveRef') }}</dt><dd>{{ item.objectiveId }}</dd>
            </template>
            <dt>{{ t('worldInteraction.quest.worldFeedback.correlation') }}</dt>
            <dd>{{ item.correlationId || t('worldInteraction.quest.worldFeedback.unavailable') }}</dd>
          </dl>
        </details>
      </li>
    </ol>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { WorldFeedbackItem } from '@/types/world'

defineProps<{ items: WorldFeedbackItem[] }>()
const { t, te, locale } = useI18n()
const reasonLabel = (reason: string) => {
  const key = `worldInteraction.quest.executionReason.${reason}`
  return te(key) ? t(key) : t('worldInteraction.quest.executionUnknownReason', { code: reason })
}
const stateLabel = (state: string) => {
  const key = `worldInteraction.quest.worldFeedback.objectiveState.${state}`
  return te(key) ? t(key) : state
}
const validTime = (value: string) => Boolean(value) && Number.isFinite(Date.parse(value))
const formatTime = (value: string) => new Intl.DateTimeFormat(locale.value, {
  dateStyle: 'medium', timeStyle: 'short',
}).format(new Date(value))
</script>

<style scoped>
.world-feedback { margin-top: 10px; overflow-wrap: anywhere; }
h4 { margin: 4px 0; }
ol { display: grid; gap: 8px; margin: 0; padding-left: 20px; }
li { min-width: 0; }
.feedback-summary { display: flex; gap: 6px; flex-wrap: wrap; align-items: baseline; }
time, summary, dl { font-size: 12px; color: var(--el-text-color-secondary); }
summary { cursor: pointer; padding: 4px 0; }
summary:focus-visible { outline: 2px solid var(--el-color-primary); outline-offset: 2px; }
dl { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 4px 8px; margin: 4px 0; }
dd { margin: 0; }
@media (max-width: 640px) {
  dl { grid-template-columns: minmax(0, 1fr); }
}
</style>
