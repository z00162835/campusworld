<script setup lang="ts">
/**
 * SpaceTable - List view table for space nodes
 * Styled to match Works page aesthetic
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSpacesStore } from '@/stores/spaces'
import type { SpaceNode } from '@/types/space'

const store = useSpacesStore()
const { t } = useI18n()

const emit = defineEmits<{
  rowClick: [node: SpaceNode]
}>()

const columns = computed(() => {
  switch (store.activeTab) {
    case 'world':
      return [
        { prop: 'name', label: t('spaces.fields.name'), width: 200 },
        { prop: 'world_type', label: t('spaces.fields.worldType'), width: 120 },
        { prop: 'status', label: t('spaces.fields.status'), width: 100 },
        { prop: 'description', label: t('spaces.fields.description') },
      ]
    case 'building':
      return [
        { prop: 'name', label: t('spaces.fields.name'), width: 180 },
        { prop: 'building_type', label: t('spaces.fields.buildingType'), width: 120 },
        { prop: 'world_id', label: t('spaces.fields.world'), width: 150 },
        { prop: 'status', label: t('spaces.fields.status'), width: 100 },
        { prop: 'description', label: t('spaces.fields.description') },
      ]
    case 'floor':
      return [
        { prop: 'name', label: t('spaces.fields.name'), width: 150 },
        { prop: 'floor_type', label: t('spaces.fields.floorType'), width: 120 },
        { prop: 'building_id', label: t('spaces.fields.building'), width: 150 },
        { prop: 'description', label: t('spaces.fields.description') },
      ]
    case 'room':
      return [
        { prop: 'name', label: t('spaces.fields.name'), width: 150 },
        { prop: 'room_type', label: t('spaces.fields.roomType'), width: 120 },
        { prop: 'floor_id', label: t('spaces.fields.floor'), width: 150 },
        { prop: 'description', label: t('spaces.fields.description') },
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
