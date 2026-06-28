<template>
  <div class="global-search">
    <el-icon><Search /></el-icon>
    <input
      v-model="query"
      type="search"
      :placeholder="t('shell.searchPlaceholder')"
      @compositionstart="isComposing = true"
      @compositionend="isComposing = false"
      @keydown.enter="onEnterKeydown"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Search } from '@element-plus/icons-vue'
import { useWorldMapStore } from '@/stores/worldMap'
import { useWorldSessionStore } from '@/stores/worldSession'

const worldSession = useWorldSessionStore()
const mapStore = useWorldMapStore()
const { t } = useI18n()
const query = ref('')
const isComposing = ref(false)

const queryBlocked = computed(
  () => worldSession.commandLoading || worldSession.sessionActionLoading,
)

function onEnterKeydown(event: KeyboardEvent) {
  if (event.isComposing || isComposing.value) return
  if (queryBlocked.value) return
  event.preventDefault()
  void submit()
}

const submit = async () => {
  const clean = query.value.trim()
  if (!clean || queryBlocked.value) return

  const submission = await worldSession.submitQuery(clean)
  if (!submission.accepted) return

  query.value = ''
  void mapStore.searchMap(clean).catch(err => {
    console.warn('[GlobalCommandSearch] map search failed:', err)
  })
  void submission.completion
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
