<script setup lang="ts">
/**
 * SpaceCard - Base card component for displaying space nodes
 * Styled to match Works page aesthetic
 */
import { computed } from 'vue'
import { Box, OfficeBuilding, List, Grid } from '@element-plus/icons-vue'
import type { SpaceNode, SpaceTab } from '@/types/space'

const props = defineProps<{
  node: SpaceNode
  type: SpaceTab
}>()

const emit = defineEmits<{
  click: [node: SpaceNode]
}>()

// Icon mapping based on type
const iconComponent = computed(() => {
  switch (props.type) {
    case 'world':
      return Box
    case 'building':
      return OfficeBuilding
    case 'floor':
      return List
    case 'room':
      return Grid
    default:
      return Box
  }
})

// Get status from attributes
const status = computed(() => {
  const attrs = props.node.attributes || {}
  if (attrs.status) return attrs.status as string
  if (attrs.building_status) return attrs.building_status as string
  return null
})

const statusClass = computed(() => {
  switch (status.value) {
    case 'active':
    case 'online':
      return 'status--active'
    case 'maintenance':
      return 'status--maintenance'
    case 'offline':
    case 'closed':
      return 'status--offline'
    default:
      return ''
  }
})

// Get display description
const displayDescription = computed(() => {
  const desc = props.node.description || ''
  return desc.length > 80 ? desc.substring(0, 80) + '...' : desc
})

// Get display tags (max 3)
const displayTags = computed(() => {
  return (props.node.tags || []).slice(0, 3)
})

const handleClick = () => {
  emit('click', props.node)
}
</script>

<template>
  <div
    class="space-card"
    :class="`space-card--${type}`"
    @click="handleClick"
  >
    <div class="space-card__header">
      <div class="space-card__icon">
        <el-icon :size="24">
          <component :is="iconComponent" />
        </el-icon>
      </div>
      <div class="space-card__title-wrap">
        <h3 class="space-card__title">{{ node.name }}</h3>
        <span v-if="status" class="space-card__status" :class="statusClass">
          {{ status }}
        </span>
      </div>
    </div>

    <div class="space-card__body">
      <p v-if="displayDescription" class="space-card__description">
        {{ displayDescription }}
      </p>

      <div v-if="displayTags.length > 0" class="space-card__tags">
        <span
          v-for="tag in displayTags"
          :key="tag"
          class="space-card__tag"
        >
          {{ tag }}
        </span>
      </div>
    </div>

    <div class="space-card__footer">
      <span class="space-card__id">ID: {{ node.id }}</span>
      <span class="space-card__action">查看详情</span>
    </div>
  </div>
</template>

<style scoped>
.space-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.space-card:hover {
  border-color: var(--border-color-dark);
  background: var(--bg-secondary);
}

.space-card__header {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-md);
}

.space-card__icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  color: var(--color-primary);
  flex-shrink: 0;
}

.space-card__title-wrap {
  flex: 1;
  min-width: 0;
}

.space-card__title {
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.space-card__status {
  display: inline-block;
  font-size: var(--font-size-xs);
  padding: 2px var(--spacing-xs);
  border-radius: var(--radius-sm);
  margin-top: var(--spacing-xs);
}

.status--active {
  background: rgba(103, 194, 58, 0.15);
  color: var(--color-success);
}

.status--maintenance {
  background: rgba(230, 162, 60, 0.15);
  color: var(--color-warning);
}

.status--offline {
  background: rgba(245, 108, 108, 0.15);
  color: var(--color-danger);
}

.space-card__body {
  flex: 1;
}

.space-card__description {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0 0 var(--spacing-sm);
}

.space-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.space-card__tag {
  font-size: var(--font-size-xs);
  padding: 2px var(--spacing-sm);
  background: var(--bg-hover);
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
}

.space-card__footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--border-color-light);
}

.space-card__id {
  font-size: var(--font-size-xs);
  color: var(--text-disabled);
}

.space-card__action {
  font-size: var(--font-size-xs);
  color: var(--color-primary);
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.space-card:hover .space-card__action {
  opacity: 1;
}
</style>
