<script setup lang="ts">
/**
 * SpacePagination - Pagination component
 * Styled to match Works page aesthetic
 */
import { useSpacesStore } from '@/stores/spaces'

const store = useSpacesStore()

// v-model:current-page is 1-indexed, store.currentPage is also 1-indexed
const handlePageChange = () => {
  // store.currentPage is already updated by v-model binding
  // Convert to offset: (page - 1) * pageSize
  const offset = (store.currentPage - 1) * store.pageSize
  store.fetchSpaces(undefined, offset, false)
}

const handleSizeChange = (size: number) => {
  store.pageSize = size
  store.currentPage = 1
  store.refresh()
}
</script>

<template>
  <div class="space-pagination">
    <el-pagination
      v-model:current-page="store.currentPage"
      v-model:page-size="store.pageSize"
      :page-sizes="[12, 24, 48, 96]"
      :total="store.currentTotal"
      :background="true"
      layout="sizes, prev, pager, next, total"
      @current-change="handlePageChange"
      @size-change="handleSizeChange"
    />
  </div>
</template>

<style scoped>
.space-pagination {
  display: flex;
  justify-content: center;
  padding: var(--spacing-xl) 0;
}

.space-pagination :deep(.el-pagination) {
  color: var(--text-secondary);
}

.space-pagination :deep(.el-pagination__total) {
  color: var(--text-tertiary);
}

.space-pagination :deep(.el-pager li) {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  margin: 0 2px;
}

.space-pagination :deep(.el-pager li:hover) {
  color: var(--text-primary);
  border-color: var(--border-color-dark);
  background: var(--bg-hover);
}

.space-pagination :deep(.el-pager li.is-active) {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #ffffff;
}

.space-pagination :deep(.el-pagination__sizes) {
  color: var(--text-secondary);
}

.space-pagination :deep(.el-pagination__sizes .el-input__wrapper) {
  background: var(--bg-secondary);
  border-color: var(--border-color);
  box-shadow: none;
}

.space-pagination :deep(.btn-prev),
.space-pagination :deep(.btn-next) {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
}

.space-pagination :deep(.btn-prev:hover),
.space-pagination :deep(.btn-next:hover) {
  color: var(--text-primary);
  border-color: var(--border-color-dark);
  background: var(--bg-hover);
}

.space-pagination :deep(.el-pagination__jump) {
  color: var(--text-tertiary);
}
</style>
