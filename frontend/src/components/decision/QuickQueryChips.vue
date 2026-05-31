<template>
  <div class="quick-chips">
    <button
      v-for="query in queries.slice(0, 4)"
      :key="query.query"
      type="button"
      @click="$emit('query', query.query)"
    >
      {{ query.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
import type { QueryHint } from '@/types/world'

defineProps<{
  queries: QueryHint[]
}>()

defineEmits<{
  query: [query: string]
}>()
</script>

<style scoped>
.quick-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}

button {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: #171b21;
  color: var(--text-secondary);
  padding: 7px 9px;
  font-size: var(--font-size-xs);
  cursor: pointer;
}

button:hover {
  color: var(--text-primary);
  border-color: var(--border-color-dark);
}
</style>
