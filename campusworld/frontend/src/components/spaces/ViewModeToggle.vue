<script setup lang="ts">
/**
 * ViewModeToggle - Switch between card and list view
 * Styled to match Works page aesthetic
 */
import { useSpacesStore } from '@/stores/spaces'
import { Grid, List } from '@element-plus/icons-vue'

const store = useSpacesStore()
</script>

<template>
  <div class="view-mode-toggle">
    <el-button-group>
      <el-button
        :type="store.viewMode === 'card' ? 'primary' : 'default'"
        @click="store.setViewMode('card')"
      >
        <el-icon><Grid /></el-icon>
      </el-button>
      <el-button
        :type="store.viewMode === 'list' ? 'primary' : 'default'"
        @click="store.setViewMode('list')"
      >
        <el-icon><List /></el-icon>
      </el-button>
    </el-button-group>
  </div>
</template>

<style scoped>
.view-mode-toggle :deep(.el-button) {
  padding: var(--spacing-sm) var(--spacing-md);
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.view-mode-toggle :deep(.el-button:hover) {
  background: var(--bg-hover);
  color: var(--text-primary);
  border-color: var(--border-color-dark);
}

.view-mode-toggle :deep(.el-button.is-active),
.view-mode-toggle :deep(.el-button--primary) {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #ffffff;
}
</style>
