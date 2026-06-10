<script setup lang="ts">
/**
 * FilterBar - Displays filters based on active tab
 * Styled to match Works page aesthetic
 */
import { ref, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSpacesStore } from '@/stores/spaces'
import {
  WORLD_STATUS_OPTIONS,
  BUILDING_TYPE_OPTIONS,
  FLOOR_TYPE_OPTIONS,
  ROOM_TYPE_OPTIONS,
  BUILDING_STATUS_OPTIONS,
  WORLD_TYPE_OPTIONS,
  getSelectOptionLabel,
} from '@/types/space'

const store = useSpacesStore()
const { t } = useI18n()

// Local filter state
const localFilters = ref({ ...store.filters })

// Fetch world options on mount (needed for building filter)
onMounted(async () => {
  await store.fetchWorlds()
})

// Watch for world_id changes to reload buildings dropdown
watch(() => localFilters.value.world_id, async (worldId) => {
  if (worldId) {
    // Clear cached buildings when world changes to get buildings for new world
    store.buildings.splice(0, store.buildings.length)
    await store.fetchBuildings(worldId)
    // Reset building and floor filters when world changes
    localFilters.value.building_id = undefined
    localFilters.value.floor_id = undefined
    store.setFilters({ world_id: worldId })
  }
})

// Watch for building_id changes to reload floors dropdown
watch(() => localFilters.value.building_id, async (buildingId) => {
  if (buildingId) {
    // Note: building_id filtering not supported by API, so we don't clear floors cache
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
        :placeholder="t('spaces.fields.worldType')"
        clearable
        @change="handleFilterChange"
      >
        <el-option
          v-for="opt in WORLD_TYPE_OPTIONS"
          :key="opt.value"
          :label="getSelectOptionLabel(opt, t)"
          :value="opt.value"
        />
      </el-select>

      <el-select
        v-model="localFilters.status"
        :placeholder="t('spaces.fields.status')"
        clearable
        multiple
        @change="handleFilterChange"
      >
        <el-option
          v-for="opt in WORLD_STATUS_OPTIONS"
          :key="opt.value"
          :label="getSelectOptionLabel(opt, t)"
          :value="opt.value"
        />
      </el-select>
    </template>

    <!-- Building Filters -->
    <template v-else-if="store.activeTab === 'building'">
      <el-select
        v-model="localFilters.world_id"
        :placeholder="t('spaces.fields.world')"
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
        :placeholder="t('spaces.fields.buildingType')"
        clearable
        @change="handleFilterChange"
      >
        <el-option
          v-for="opt in BUILDING_TYPE_OPTIONS"
          :key="opt.value"
          :label="getSelectOptionLabel(opt, t)"
          :value="opt.value"
        />
      </el-select>

      <el-select
        v-model="localFilters.status"
        :placeholder="t('spaces.fields.status')"
        clearable
        multiple
        @change="handleFilterChange"
      >
        <el-option
          v-for="opt in BUILDING_STATUS_OPTIONS"
          :key="opt.value"
          :label="getSelectOptionLabel(opt, t)"
          :value="opt.value"
        />
      </el-select>
    </template>

    <!-- Floor Filters -->
    <template v-else-if="store.activeTab === 'floor'">
      <el-select
        v-model="localFilters.building_id"
        :placeholder="t('spaces.fields.building')"
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
        :placeholder="t('spaces.fields.floorType')"
        clearable
        @change="handleFilterChange"
      >
        <el-option
          v-for="opt in FLOOR_TYPE_OPTIONS"
          :key="opt.value"
          :label="getSelectOptionLabel(opt, t)"
          :value="opt.value"
        />
      </el-select>
    </template>

    <!-- Room Filters -->
    <template v-else-if="store.activeTab === 'room'">
      <el-select
        v-model="localFilters.floor_id"
        :placeholder="t('spaces.fields.floor')"
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
        :placeholder="t('spaces.fields.roomType')"
        clearable
        @change="handleFilterChange"
      >
        <el-option
          v-for="opt in ROOM_TYPE_OPTIONS"
          :key="opt.value"
          :label="getSelectOptionLabel(opt, t)"
          :value="opt.value"
        />
      </el-select>
    </template>

    <!-- Reset Button -->
    <el-button @click="handleReset">{{ t('common.reset') }}</el-button>
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
