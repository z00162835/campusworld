<script setup lang="ts">
/**
 * SpaceTable - List view table for space nodes
 * Styled to match Works page aesthetic
 */
import { computed } from 'vue'
import { useSpacesStore } from '@/stores/spaces'
import type { SpaceNode } from '@/types/space'

const store = useSpacesStore()

const emit = defineEmits<{
  rowClick: [node: SpaceNode]
}>()

const columns = computed(() => {
  switch (store.activeTab) {
    case 'world':
      return [
        { prop: 'name', label: '名称', width: 200 },
        { prop: 'world_type', label: '世界类型', width: 120 },
        { prop: 'status', label: '状态', width: 100 },
        { prop: 'description', label: '描述' },
      ]
    case 'building':
      return [
        { prop: 'name', label: '名称', width: 180 },
        { prop: 'building_type', label: '建筑类型', width: 120 },
        { prop: 'world_id', label: '所属世界', width: 150 },
        { prop: 'status', label: '状态', width: 100 },
        { prop: 'description', label: '描述' },
      ]
    case 'floor':
      return [
        { prop: 'name', label: '名称', width: 150 },
        { prop: 'floor_type', label: '楼层类型', width: 120 },
        { prop: 'building_id', label: '所属建筑', width: 150 },
        { prop: 'description', label: '描述' },
      ]
    case 'room':
      return [
        { prop: 'name', label: '名称', width: 150 },
        { prop: 'room_type', label: '房间类型', width: 120 },
        { prop: 'floor_id', label: '所属楼层', width: 150 },
        { prop: 'description', label: '描述' },
      ]
    default:
      return []
  }
})
</script>

<template>
  <div class="space-table">
    <el-table
      :data="store.currentNodes"
      stripe
      highlight-current-row
      style="width: 100%"
      @row-click="(row: SpaceNode) => emit('rowClick', row)"
    >
      <el-table-column
        v-for="col in columns"
        :key="col.prop"
        :prop="col.prop"
        :label="col.label"
        :width="col.width"
      >
        <template #default="{ row }">
          <span class="cell-name">{{ row.name }}</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.space-table {
  width: 100%;
}

.space-table :deep(.el-table) {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

.space-table :deep(.el-table tr) {
  background: var(--bg-secondary);
}

.space-table :deep(.el-table th.el-table__cell) {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  font-weight: var(--font-weight-semibold);
  font-size: var(--font-size-sm);
  border-bottom: 1px solid var(--border-color);
}

.space-table :deep(.el-table td.el-table__cell) {
  border-bottom: 1px solid var(--border-color-light);
  color: var(--text-primary);
}

.space-table :deep(.el-table__body tr:hover > td.el-table__cell) {
  background: var(--bg-hover);
}

.space-table :deep(.el-table__row.current-row > td.el-table__cell) {
  background: var(--bg-hover);
}

.space-table :deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background: var(--bg-tertiary);
}

.space-table :deep(.el-table .el-table__cell) {
  padding: var(--spacing-md) 0;
}

.cell-name {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
}
</style>
