<script setup lang="ts">
/**
 * GlobalSearch - Search input with debounce
 * Styled to match Works page aesthetic
 */
import { ref, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { useSpacesStore } from '@/stores/spaces'

const store = useSpacesStore()
const searchValue = ref('')
let debounceTimer: ReturnType<typeof setTimeout> | null = null

watch(searchValue, (val) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    store.setSearchKeyword(val)
  }, 300)
})
</script>

<template>
  <el-input
    v-model="searchValue"
    :prefix-icon="Search"
    :placeholder="$t('spaces.search.placeholder')"
    clearable
    class="global-search"
  />
</template>

<style scoped>
.global-search {
  width: 200px;
}

.global-search :deep(.el-input__wrapper) {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: none;
  transition: all var(--transition-fast);
}

.global-search :deep(.el-input__wrapper:hover) {
  border-color: var(--border-color-dark);
}

.global-search :deep(.el-input__wrapper.is-focus) {
  border-color: var(--color-primary);
}

.global-search :deep(.el-input__inner) {
  color: var(--text-primary);
}

.global-search :deep(.el-input__inner::placeholder) {
  color: var(--text-placeholder);
}

.global-search :deep(.el-icon) {
  color: var(--text-tertiary);
}
</style>
