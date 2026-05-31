<template>
  <header class="world-topbar">
    <el-dropdown trigger="click" @command="handleWorldCommand">
      <button class="world-anchor" type="button">
        <span>CampusWorld</span>
        <span class="world-name">{{ currentWorldLabel }}</span>
        <el-icon><ArrowDown /></el-icon>
      </button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item disabled>
            {{ currentLocationHint }}
          </el-dropdown-item>
          <el-dropdown-item
            v-for="world in worldSession.availableWorlds"
            :key="world.world_id"
            :command="`enter:${world.world_id}`"
            :disabled="world.is_current"
          >
            {{ world.is_recommended ? '★ ' : '' }}{{ world.name }}
          </el-dropdown-item>
          <el-dropdown-item v-if="!worldSession.availableWorlds.length" disabled>
            No worlds available
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>

    <global-command-search class="top-search" />

    <el-select
      :model-value="worldSession.viewMode"
      class="view-mode"
      size="small"
      @change="onViewModeChange"
    >
      <el-option :label="t('worldInteraction.viewMode.focus')" value="Focus" />
      <el-option :label="t('worldInteraction.viewMode.map')" value="Map" />
    </el-select>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import GlobalCommandSearch from './GlobalCommandSearch.vue'
import { useWorldSessionStore } from '@/stores/worldSession'

import type { ViewMode } from '@/types/world'

const { t } = useI18n()
const worldSession = useWorldSessionStore()

const onViewModeChange = (mode: ViewMode) => {
  worldSession.setViewMode(mode)
}

const currentSpaceName = computed(() => {
  return (
    worldSession.contextSummary?.currentSpace?.name
    || worldSession.decisionCenter?.focus?.title
    || null
  )
})

const recommendedWorld = computed(() => {
  return worldSession.availableWorlds.find(world => world.is_recommended) || null
})

const currentWorldLabel = computed(() => {
  if (worldSession.currentWorld?.name) {
    return worldSession.currentWorld.name
  }
  if (recommendedWorld.value && currentSpaceName.value) {
    return `${currentSpaceName.value} · ${recommendedWorld.value.name}`
  }
  if (recommendedWorld.value) {
    return recommendedWorld.value.name
  }
  return currentSpaceName.value || 'CampusWorld Hub'
})

const currentLocationHint = computed(() => {
  const space = currentSpaceName.value || 'Unknown location'
  if (worldSession.currentWorld) {
    return `In world: ${worldSession.currentWorld.name} · ${space}`
  }
  const enterHint = recommendedWorld.value?.name || 'a world'
  return `At ${space} · Enter ${enterHint} to begin`
})

const handleWorldCommand = async (command: string) => {
  if (command === 'leave') {
    await worldSession.leaveWorld()
    return
  }
  if (command.startsWith('enter:')) {
    const worldId = command.slice('enter:'.length)
    if (worldId === '__campus_hub__') {
      await worldSession.leaveWorld()
      return
    }
    await worldSession.enterWorld(worldId)
  }
}
</script>

<style scoped>
.world-topbar {
  height: 52px;
  display: grid;
  grid-template-columns: minmax(220px, auto) minmax(240px, 1fr) 112px;
  align-items: center;
  gap: var(--spacing-md);
  padding: 0 var(--spacing-lg);
  background: #171a20;
  border-bottom: 1px solid var(--border-color);
}

.world-anchor {
  border: 0;
  background: transparent;
  color: var(--text-primary);
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-sm);
  cursor: pointer;
  min-width: 0;
}

.world-name {
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.top-search {
  min-width: 0;
}

.view-mode {
  width: 112px;
}

@media (max-width: 720px) {
  .world-topbar {
    grid-template-columns: minmax(130px, 1fr) 96px;
    gap: var(--spacing-sm);
  }

  .top-search {
    display: none;
  }

  .view-mode {
    width: 96px;
  }
}
</style>
