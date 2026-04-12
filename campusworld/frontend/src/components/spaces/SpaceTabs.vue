<script setup lang="ts">
/**
 * SpaceTabs - Tab switching for space types
 * Styled to match Works page aesthetic
 */
import { useSpacesStore } from '@/stores/spaces'

const store = useSpacesStore()

const tabs = [
  { key: 'world', label: 'spaces.tabs.world' },
  { key: 'building', label: 'spaces.tabs.building' },
  { key: 'floor', label: 'spaces.tabs.floor' },
  { key: 'room', label: 'spaces.tabs.room' },
] as const

const handleTabChange = (tab: typeof tabs[number]['key']) => {
  store.setActiveTab(tab)
}
</script>

<template>
  <div class="space-tabs">
    <el-radio-group
      :model-value="store.activeTab"
      @update:model-value="handleTabChange"
    >
      <el-radio-button
        v-for="tab in tabs"
        :key="tab.key"
        :value="tab.key"
      >
        {{ $t(tab.label) }}
      </el-radio-button>
    </el-radio-group>
  </div>
</template>

<style scoped>
.space-tabs {
  margin-bottom: var(--spacing-md);
}

.space-tabs :deep(.el-radio-button__inner) {
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.space-tabs :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #ffffff;
  box-shadow: none;
}

.space-tabs :deep(.el-radio-button:first-child .el-radio-button__inner) {
  border-radius: var(--radius-sm);
}

.space-tabs :deep(.el-radio-button:last-child .el-radio-button__inner) {
  border-radius: var(--radius-sm);
}

.space-tabs :deep(.el-radio-button:hover .el-radio-button__inner) {
  color: var(--text-primary);
  background: var(--bg-hover);
}
</style>
