<template>
  <article class="task-card">
    <div class="task-header">
      <h3>{{ task.title }}</h3>
      <span>{{ task.progress }}%</span>
    </div>
    <p>{{ task.summary }}</p>
    <el-progress :percentage="task.progress" :show-text="false" />
    <div class="step">
      <span>Current step</span>
      <strong>{{ task.currentStep.title }}</strong>
      <p>{{ task.currentStep.shortInstruction }}</p>
    </div>
    <el-button type="primary" size="small" @click="$emit('execute', task.nextBestAction.id)">
      {{ task.nextBestAction.label }}
    </el-button>
  </article>
</template>

<script setup lang="ts">
import type { TaskCard } from '@/types/world'

defineProps<{
  task: TaskCard
}>()

defineEmits<{
  execute: [optionId: string]
}>()
</script>

<style scoped>
.task-card {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: #1b1f26;
  padding: var(--spacing-lg);
}

.task-header {
  display: flex;
  justify-content: space-between;
  gap: var(--spacing-md);
}

h3 {
  margin: 0;
  font-size: var(--font-size-base);
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
  margin-bottom: var(--spacing-xs);
}
</style>
