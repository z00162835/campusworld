<template>
  <div class="global-search">
    <el-icon><Search /></el-icon>
    <input
      v-model="query"
      type="search"
      placeholder="Search spaces, Agents, tasks, or commands"
      @compositionstart="isComposing = true"
      @compositionend="isComposing = false"
      @keydown.enter="onEnterKeydown"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { useWorldSessionStore } from '@/stores/worldSession'

const worldSession = useWorldSessionStore()
const query = ref('')
const isComposing = ref(false)

function onEnterKeydown(event: KeyboardEvent) {
  if (event.isComposing || isComposing.value) return
  event.preventDefault()
  void submit()
}

const submit = async () => {
  const clean = query.value.trim()
  if (!clean) return
  query.value = ''
  await worldSession.submitQuery(clean)
}
</script>

<style scoped>
.global-search {
  height: 34px;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 0 var(--spacing-md);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-tertiary);
}

.global-search input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-size: var(--font-size-sm);
}
</style>
