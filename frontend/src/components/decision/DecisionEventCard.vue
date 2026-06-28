<template>
  <article class="event-card" :class="stripeClass">
    <div class="event-header">
      <h3>{{ event.title }}</h3>
      <span :class="['priority', event.priority]">{{ event.priority }}</span>
    </div>
    <p class="event-summary">{{ event.summary }}</p>
    <details v-if="event.impact || event.recommendation" class="event-details">
      <summary>{{ t('worldInteraction.decision.eventDetails') }}</summary>
      <dl>
        <template v-if="event.impact">
          <dt>{{ t('worldInteraction.decision.eventImpact') }}</dt>
          <dd>{{ event.impact }}</dd>
        </template>
        <template v-if="event.recommendation">
          <dt>{{ t('worldInteraction.decision.eventRecommendation') }}</dt>
          <dd>{{ event.recommendation }}</dd>
        </template>
      </dl>
    </details>
    <div class="actions">
      <el-button
        v-for="option in event.options"
        :key="option.id"
        :type="buttonType(option.style)"
        size="small"
        :plain="option.style !== 'primary'"
        :disabled="worldSession.sessionActionBusy"
        @click="$emit('execute', event.id, option.id)"
      >
        {{ option.label }}
      </el-button>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useWorldSessionStore } from '@/stores/worldSession'
import type { DecisionEvent, DecisionOption } from '@/types/world'

const props = defineProps<{
  event: DecisionEvent
}>()

defineEmits<{
  execute: [eventId: string, optionId: string]
}>()

const { t } = useI18n()
const worldSession = useWorldSessionStore()

const stripeClass = computed(() => {
  const map: Record<DecisionEvent['priority'], string> = {
    urgent: 'severity-stripe--critical',
    important: 'severity-stripe--warning',
    normal: 'severity-stripe--info',
    low: 'severity-stripe--normal',
  }
  return map[props.event.priority] ?? 'severity-stripe--info'
})

const buttonType = (style: DecisionOption['style']) => {
  if (style === 'danger') return 'danger'
  if (style === 'safe') return 'success'
  if (style === 'primary') return 'primary'
  return 'default'
}
</script>

<style scoped>
.event-card {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--decision-card-bg);
  padding: var(--spacing-lg);
  border-left-width: var(--decision-severity-stripe-width);
  border-left-style: solid;
}

.severity-stripe--critical {
  border-left-color: var(--decision-severity-critical);
}

.severity-stripe--warning {
  border-left-color: var(--decision-severity-warning);
}

.severity-stripe--info {
  border-left-color: var(--decision-severity-info);
}

.severity-stripe--normal {
  border-left-color: var(--decision-severity-normal);
}

.event-header {
  display: flex;
  justify-content: space-between;
  gap: var(--spacing-md);
  align-items: flex-start;
}

h3 {
  margin: 0;
  font-size: var(--font-size-lg);
}

.event-summary {
  margin: var(--spacing-sm) 0 var(--spacing-md);
  color: var(--text-secondary);
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.event-details {
  margin-bottom: var(--spacing-md);
  font-size: var(--font-size-sm);
}

.event-details summary {
  cursor: pointer;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  text-transform: uppercase;
  user-select: none;
}

.event-details summary:hover {
  color: var(--text-secondary);
}

dl {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: var(--spacing-xs) var(--spacing-md);
  margin: var(--spacing-sm) 0 0;
}

dt {
  color: var(--text-tertiary);
}

dd {
  margin: 0;
  color: var(--text-secondary);
}

.priority {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  text-transform: uppercase;
}

.priority.urgent {
  color: var(--color-danger);
}

.actions {
  display: flex;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
}
</style>
