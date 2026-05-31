<template>
  <article class="event-card">
    <div class="event-header">
      <h3>{{ event.title }}</h3>
      <span :class="['priority', event.priority]">{{ event.priority }}</span>
    </div>
    <p>{{ event.summary }}</p>
    <dl>
      <dt>Impact</dt>
      <dd>{{ event.impact }}</dd>
      <dt>Recommendation</dt>
      <dd>{{ event.recommendation }}</dd>
    </dl>
    <div class="actions">
      <el-button
        v-for="option in event.options"
        :key="option.id"
        :type="buttonType(option.style)"
        size="small"
        :plain="option.style !== 'primary'"
        @click="$emit('execute', event.id, option.id)"
      >
        {{ option.label }}
      </el-button>
    </div>
  </article>
</template>

<script setup lang="ts">
import type { DecisionEvent, DecisionOption } from '@/types/world'

defineProps<{
  event: DecisionEvent
}>()

defineEmits<{
  execute: [eventId: string, optionId: string]
}>()

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
  background: #1b1f26;
  padding: var(--spacing-lg);
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

p {
  margin: var(--spacing-sm) 0 var(--spacing-md);
  color: var(--text-secondary);
  line-height: 1.55;
}

dl {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: var(--spacing-xs) var(--spacing-md);
  margin: 0 0 var(--spacing-md);
  font-size: var(--font-size-sm);
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
