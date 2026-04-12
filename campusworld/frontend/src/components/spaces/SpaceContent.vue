<script setup lang="ts">
/**
 * SpaceContent - Card or list view container
 * Styled to match Works page aesthetic
 */
import { useSpacesStore } from '@/stores/spaces'
import { WorldCard, BuildingCard, FloorCard, RoomCard } from './cards'
import SpaceTable from './SpaceTable.vue'
import SpacePagination from './SpacePagination.vue'
import type { SpaceNode } from '@/types/space'

const store = useSpacesStore()

const emit = defineEmits<{
  cardClick: [node: SpaceNode]
}>()

const getNodeKey = (node: SpaceNode) => node.id
</script>

<template>
  <div class="space-content">
    <!-- Loading State -->
    <div v-if="store.loading" class="loading-container">
      <div v-for="i in 6" :key="i" class="skeleton-card"></div>
    </div>

    <!-- Empty State -->
    <div v-else-if="store.currentNodes.length === 0" class="empty-container">
      <el-empty :description="$t('spaces.empty.description')" />
    </div>

    <!-- Card View -->
    <template v-else-if="store.viewMode === 'card'">
      <div class="card-grid">
        <template v-if="store.activeTab === 'world'">
          <WorldCard
            v-for="node in store.currentNodes"
            :key="getNodeKey(node)"
            :node="node as any"
            @click="emit('cardClick', node)"
          />
        </template>
        <template v-else-if="store.activeTab === 'building'">
          <BuildingCard
            v-for="node in store.currentNodes"
            :key="getNodeKey(node)"
            :node="node as any"
            @click="emit('cardClick', node)"
          />
        </template>
        <template v-else-if="store.activeTab === 'floor'">
          <FloorCard
            v-for="node in store.currentNodes"
            :key="getNodeKey(node)"
            :node="node as any"
            @click="emit('cardClick', node)"
          />
        </template>
        <template v-else>
          <RoomCard
            v-for="node in store.currentNodes"
            :key="getNodeKey(node)"
            :node="node as any"
            @click="emit('cardClick', node)"
          />
        </template>
      </div>
      <SpacePagination />
    </template>

    <!-- List View -->
    <template v-else>
      <div class="list-container">
        <SpaceTable @row-click="emit('cardClick', $event)" />
      </div>
      <SpacePagination />
    </template>
  </div>
</template>

<style scoped>
.space-content {
  min-height: 400px;
}

.loading-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--spacing-md);
}

.skeleton-card {
  height: 160px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.empty-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 300px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--spacing-md);
}

.list-container {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
}
</style>
