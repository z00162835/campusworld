<template>
  <article class="task-card">
    <div class="task-header">
      <div class="task-title-row">
        <h3>{{ task.title }}</h3>
        <span class="task-status-pill">{{ task.status }}</span>
      </div>
      <span class="task-progress-label">{{ task.progress }}%</span>
    </div>
    <p>{{ task.summary }}</p>
    <el-progress :percentage="task.progress" :show-text="false" />
    <div class="step">
      <span>{{ t('worldInteraction.decision.currentStep') }}</span>
      <strong>{{ task.currentStep.title }}</strong>
      <p>{{ task.currentStep.shortInstruction }}</p>
    </div>
    <el-button
      type="primary"
      size="small"
      :disabled="worldSession.sessionActionBusy"
      @click="$emit('execute', task.nextBestAction.id)"
    >
      {{ task.nextBestAction.label }}
    </el-button>
  </article>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useWorldSessionStore } from '@/stores/worldSession'
import type { TaskCard } from '@/types/world'

defineProps<{
  task: TaskCard
}>()

defineEmits<{
  execute: [optionId: string]
}>()

const { t } = useI18n()
const worldSession = useWorldSessionStore()
</script>

<style scoped>
.task-card {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--decision-card-bg);
  padding: var(--spacing-lg);
  border-top: 2px solid var(--color-primary);
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
</style>
