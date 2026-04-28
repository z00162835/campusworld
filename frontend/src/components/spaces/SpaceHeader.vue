<script setup lang="ts">
/**
 * SpaceHeader - Page header with search and view toggle
 * Styled to match Works page aesthetic
 */
import { ref, watch } from 'vue'
import { useSpacesStore } from '@/stores/spaces'
import GlobalSearch from './GlobalSearch.vue'
import ViewModeToggle from './ViewModeToggle.vue'

const store = useSpacesStore()

const searchKeyword = ref('')

watch(searchKeyword, (val) => {
  store.setSearchKeyword(val)
})
</script>

<template>
  <div class="space-header">
    <div class="header-left">
      <h2 class="page-title">{{ $t(`spaces.tabs.${store.activeTab}`) }}</h2>
      <span class="total-count">{{ store.currentTotal }} {{ $t('spaces.items') }}</span>
    </div>
    <div class="header-right">
      <GlobalSearch />
      <ViewModeToggle />
    </div>
  </div>
</template>

<style scoped>
.space-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-lg);
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: var(--spacing-md);
}

.page-title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

.total-count {
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}
</style>
