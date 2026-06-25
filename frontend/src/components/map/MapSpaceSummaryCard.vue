<template>
  <section class="map-space-summary" :class="{ embedded }">
    <header class="summary-header">
      <h3>{{ summary.space_node.name }}</h3>
      <el-button size="small" text @click="mapStore.clearMapSelection()">
        {{ t('worldInteraction.map.spaceSummary.close') }}
      </el-button>
    </header>

    <div v-if="summary.section1_appearance.lines.length" class="summary-block">
      <h4>{{ t('worldInteraction.map.spaceSummary.appearance') }}</h4>
      <p v-for="(line, index) in summary.section1_appearance.lines" :key="`s1-${index}`">{{ line }}</p>
    </div>

    <div v-if="summary.section2_occupants.length" class="summary-block">
      <h4>{{ t('worldInteraction.map.spaceSummary.occupants') }}</h4>
      <ul>
        <li v-for="row in summary.section2_occupants" :key="`occ-${row.id}`">{{ row.name }}</li>
      </ul>
    </div>

    <div v-if="summary.section3_devices.length" class="summary-block">
      <h4>{{ t('worldInteraction.map.spaceSummary.devices') }}</h4>
      <ul>
        <li v-for="row in summary.section3_devices" :key="`dev-${row.id}`">{{ row.name }} ({{ row.status }})</li>
      </ul>
    </div>

    <div v-if="summary.section4_next_or_adjacent.length" class="summary-block">
      <h4>{{ t('worldInteraction.map.spaceSummary.exits') }}</h4>
      <ul>
        <li v-for="row in summary.section4_next_or_adjacent" :key="`exit-${row.id}`">
          <button type="button" class="exit-link" @click="mapStore.selectEntity(String(row.id))">
            <span v-if="row.direction">{{ directionLabel(row.direction) }} · </span>{{ row.name }}
          </button>
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useWorldMapStore } from '@/stores/worldMap'
import { formatDirectionLabel } from '@/utils/mapLayout'
import type { SpaceSummaryData } from '@/types/world'

defineProps<{
  summary: SpaceSummaryData
  embedded?: boolean
}>()

const { t } = useI18n()
const mapStore = useWorldMapStore()

const directionLabel = (direction?: string | null) => formatDirectionLabel(direction || undefined, t)
</script>

<style scoped>
.map-space-summary.embedded {
  margin-bottom: 0;
  padding: 0;
  border: 0;
  background: transparent;
}

.exit-link {
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  padding: 0;
  text-align: left;
}

.map-space-summary {
  margin-bottom: var(--spacing-md);
  padding: var(--spacing-md);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: rgba(29, 34, 41, 0.92);
}

.summary-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
}

.summary-header h3 {
  margin: 0;
  font-size: var(--font-size-base);
}

.summary-block {
  margin-top: var(--spacing-sm);
}

.summary-block h4 {
  margin: 0 0 4px;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.summary-block p,
.summary-block li {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.summary-block ul {
  margin: 0;
  padding-left: 1.1rem;
}
</style>
