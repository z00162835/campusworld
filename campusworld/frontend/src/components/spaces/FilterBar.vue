<script setup lang="ts">
/**
 * FilterBar - Displays filters based on active tab
 * Styled to match Works page aesthetic
 */
import { ref, watch, onMounted } from 'vue'
import { useSpacesStore } from '@/stores/spaces'
import {
  WORLD_STATUS_OPTIONS,
  BUILDING_TYPE_OPTIONS,
  FLOOR_TYPE_OPTIONS,
  ROOM_TYPE_OPTIONS,
  BUILDING_STATUS_OPTIONS,
} from '@/types/space'

const store = useSpacesStore()

// Local filter state
const localFilters = ref({ ...store.filters })

// Fetch dropdown options when needed
onMounted(async () => {
  await store.fetchWorlds()
})

// Watch for tab changes to load appropriate dropdown data
watch(() => store.activeTab, async (tab) => {
  if (tab === 'building' || tab === 'floor' || tab === 'room') {
    await store.fetchBuildings(localFilters.value.world_id)
  }
  if (tab === 'floor' || tab === 'room') {
    await store.fetchFloors()
  }
}, { immediate: true })

// Watch for world_id changes to reload buildings
watch(() => localFilters.value.world_id, async (worldId) => {
  if (worldId) {
    await store.fetchBuildings(worldId)
    // Reset building and floor filters when world changes
    localFilters.value.building_id = undefined
    localFilters.value.floor_id = undefined
    store.setFilters({ world_id: worldId })
  }
})

// Watch for building_id changes to reload floors
watch(() => localFilters.value.building_id, async (buildingId) => {
  if (buildingId) {
    await store.fetchFloors()
    // Reset floor filter when building changes
    localFilters.value.floor_id = undefined
    store.setFilters({ building_id: buildingId })
  }
})

const handleFilterChange = () => {
  store.setFilters(localFilters.value)
  store.refresh()
}

const handleReset = () => {
  localFilters.value = {}
  store.resetFilters()
  store.refresh()
}

// Options for dropdowns based on store data
const worldOptions = () => store.worlds.map(w => ({ label: w.name, value: w.id }))
const buildingOptions = () => store.buildings.map(b => ({ label: b.name, value: b.id }))
const floorOptions = () => store.floors.map(f => ({ label: f.name, value: f.id }))
</script>

<template>
  <div class="filter-bar">
    <!-- World Filters -->
    <template v-if="store.activeTab === 'world'">
      <el-select
        v-model="localFilters.world_type"
        placeholder="世界类型"
        clearable
        @change="handleFilterChange"
      >
        <el-option
          v-for="opt in ['virtual', 'physical', 'mixed']"
          :key="opt"
          :label="opt"
          :value="opt"
        />
      </el-select>

      <el-select
        v-model="localFilters.status"
        placeholder="状态"
        clearable
        multiple
        @change="handleFilterChange"
      >
        <el-option
          v-for="opt in WORLD_STATUS_OPTIONS"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
    </template>

    <!-- Building Filters -->
    <template v-else-if="store.activeTab === 'building'">
      <el-select
        v-model="localFilters.world_id"
        placeholder="所属世界"
        clearable
        @change="handleFilterChange"
      >
        <el-option
          v-for="opt in worldOptions()"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>

      <el-select
        v-model="localFilters.building_type"
        placeholder="建筑类型"
        clearable
        @change="handleFilterChange"
      >
        <el-option
          v-for="opt in BUILDING_TYPE_OPTIONS"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>

      <el-select
        v-model="localFilters.status"
        placeholder="状态"
        clearable
        multiple
        @change="handleFilterChange"
      >
        <el-option
          v-for="opt in BUILDING_STATUS_OPTIONS"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
    </template>

    <!-- Floor Filters -->
    <template v-else-if="store.activeTab === 'floor'">
      <el-select
        v-model="localFilters.building_id"
        placeholder="所属建筑"
        clearable
        @change="handleFilterChange"
      >
        <el-option
          v-for="opt in buildingOptions()"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>

      <el-select
        v-model="localFilters.floor_type"
        placeholder="楼层类型"
        clearable
        @change="handleFilterChange"
      >
        <el-option
          v-for="opt in FLOOR_TYPE_OPTIONS"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
    </template>

    <!-- Room Filters -->
    <template v-else-if="store.activeTab === 'room'">
      <el-select
        v-model="localFilters.floor_id"
        placeholder="所属楼层"
        clearable
        @change="handleFilterChange"
      >
        <el-option
          v-for="opt in floorOptions()"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>

      <el-select
        v-model="localFilters.room_type"
        placeholder="房间类型"
        clearable
        @change="handleFilterChange"
      >
        <el-option
          v-for="opt in ROOM_TYPE_OPTIONS"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
    </template>

    <!-- Reset Button -->
    <el-button @click="handleReset">重置</el-button>
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  gap: var(--spacing-md);
  flex-wrap: wrap;
  align-items: center;
  padding: var(--spacing-md);
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-md);
}

.filter-bar :deep(.el-select) {
  width: 160px;
}

.filter-bar :deep(.el-select .el-input__wrapper) {
  background: var(--bg-secondary);
  border-color: var(--border-color);
  box-shadow: none;
}

.filter-bar :deep(.el-select .el-input__wrapper:hover) {
  border-color: var(--border-color-dark);
}

.filter-bar :deep(.el-select .el-input__wrapper.is-focus) {
  border-color: var(--color-primary);
}

.filter-bar :deep(.el-button) {
  background: var(--bg-secondary);
  border-color: var(--border-color);
  color: var(--text-secondary);
}

.filter-bar :deep(.el-button:hover) {
  background: var(--bg-hover);
  border-color: var(--border-color-dark);
  color: var(--text-primary);
}
</style>
