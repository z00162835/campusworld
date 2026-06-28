<template>
  <header class="world-topbar">
    <el-dropdown
      trigger="click"
      effect="dark"
      popper-class="cw-dropdown-popper"
      @command="handleWorldCommand"
    >
      <button class="world-anchor" type="button" :disabled="worldSession.sessionActionBusy">
        <span class="world-name">{{ currentWorldLabel }}</span>
        <el-icon><ArrowDown /></el-icon>
      </button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item
            v-for="world in worldMenuItems"
            :key="world.world_id"
            :command="worldCommand(world.world_id)"
            :class="{ 'is-active': world.is_current }"
            :disabled="worldSession.sessionActionBusy || world.is_current"
          >
            {{ world.name }}
          </el-dropdown-item>
          <el-dropdown-item v-if="!worldMenuItems.length" disabled>
            {{ t('worldInteraction.worlds.empty') }}
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>

    <global-command-search class="top-search" />

    <el-dropdown
      trigger="click"
      effect="dark"
      popper-class="cw-dropdown-popper"
      @command="onViewModeCommand"
    >
      <button class="view-mode-trigger" type="button">
        <span>{{ viewModeLabel }}</span>
        <el-icon><ArrowDown /></el-icon>
      </button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item
            v-for="mode in viewModes"
            :key="mode"
            :command="mode"
            :class="{ 'is-active': worldSession.viewMode === mode }"
          >
            {{ t(`worldInteraction.viewMode.${mode.toLowerCase()}`) }}
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import GlobalCommandSearch from './GlobalCommandSearch.vue'
import { useWorldSessionStore } from '@/stores/worldSession'
import { CAMPUS_HUB_WORLD_ID, type ViewMode } from '@/types/world'

const { t } = useI18n()
const worldSession = useWorldSessionStore()

const viewModes: ViewMode[] = ['Focus', 'Map']

const hubWorld = computed(() => {
  return worldSession.availableWorlds.find(world => world.world_id === CAMPUS_HUB_WORLD_ID) || null
})

const worldMenuItems = computed(() => {
  const items = [...worldSession.availableWorlds]
  return items.sort((a, b) => {
    if (a.world_id === CAMPUS_HUB_WORLD_ID) return -1
    if (b.world_id === CAMPUS_HUB_WORLD_ID) return 1
    return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
  })
})

const currentWorldLabel = computed(() => {
  if (worldSession.currentWorld?.name) {
    return worldSession.currentWorld.name
  }
  return hubWorld.value?.name || t('worldInteraction.hub.defaultName')
})

const viewModeLabel = computed(() => {
  return t(`worldInteraction.viewMode.${worldSession.viewMode.toLowerCase()}`)
})

const worldCommand = (worldId: string) => `enter:${worldId}`

const onViewModeCommand = (mode: ViewMode) => {
  worldSession.setViewMode(mode)
}

const handleWorldCommand = async (command: string) => {
  if (worldSession.sessionActionBusy) return
  if (command === 'leave') {
    await worldSession.leaveWorld()
    return
  }
  if (command.startsWith('enter:')) {
    const worldId = command.slice('enter:'.length)
    if (worldId === CAMPUS_HUB_WORLD_ID) {
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
  grid-template-columns: minmax(220px, auto) minmax(240px, 1fr) minmax(96px, auto);
  align-items: center;
  gap: var(--spacing-md);
  padding: 0 var(--spacing-lg);
  background: #171a20;
  border-bottom: 1px solid var(--border-color);
}

.world-anchor:disabled,
.view-mode-trigger:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.world-anchor,
.view-mode-trigger {
  border: 0;
  background: transparent;
  color: var(--text-primary);
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-sm);
  cursor: pointer;
  min-width: 0;
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-md);
}

.world-anchor:hover,
.view-mode-trigger:hover {
  background: var(--bg-hover);
}

.world-name {
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
}

.view-mode-trigger {
  justify-content: space-between;
  min-width: 96px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.view-mode-trigger:hover {
  color: var(--text-primary);
}

.top-search {
  min-width: 0;
}

@media (max-width: 720px) {
  .world-topbar {
    grid-template-columns: minmax(130px, 1fr) minmax(88px, auto);
    gap: var(--spacing-sm);
  }

  .top-search {
    display: none;
  }

  .view-mode-trigger {
    min-width: 88px;
  }
}
</style>
