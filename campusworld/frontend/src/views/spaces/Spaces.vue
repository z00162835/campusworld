<script setup lang="ts">
/**
 * Spaces - Main spaces page
 * Styled to match Works page aesthetic
 */
import { ref, onMounted } from 'vue'
import { useSpacesStore } from '@/stores/spaces'
import SpaceHeader from '@/components/spaces/SpaceHeader.vue'
import SpaceTabs from '@/components/spaces/SpaceTabs.vue'
import FilterBar from '@/components/spaces/FilterBar.vue'
import SpaceContent from '@/components/spaces/SpaceContent.vue'
import SpaceDetailDrawer from '@/components/spaces/SpaceDetailDrawer.vue'
import type { SpaceNode } from '@/types/space'

const store = useSpacesStore()

const drawerVisible = ref(false)
const selectedNode = ref<SpaceNode | null>(null)

onMounted(() => {
  store.fetchSpaces()
})

const handleCardClick = (node: SpaceNode) => {
  selectedNode.value = node
  drawerVisible.value = true
}

const handleRefresh = () => {
  store.refresh()
}
</script>

<template>
  <div class="spaces-page">
    <div class="spaces-container">
      <SpaceHeader />
      <div class="spaces-section">
        <SpaceTabs />
        <FilterBar />
      </div>
      <SpaceContent @card-click="handleCardClick" />
      <SpaceDetailDrawer
        v-model:visible="drawerVisible"
        :node="selectedNode"
        @refresh="handleRefresh"
      />
    </div>
  </div>
</template>

<style scoped>
.spaces-page {
  width: 100%;
  height: 100%;
  overflow-y: auto;
}

.spaces-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: var(--spacing-xl);
}

.spaces-section {
  margin-bottom: var(--spacing-lg);
}
</style>
