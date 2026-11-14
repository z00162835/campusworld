<template>
  <details v-if="hasContent" class="quest-journal">
    <summary>{{ t('worldInteraction.quest.journal') }}</summary>
    <div class="quest-journal__graph" role="list">
      <div v-for="node in journal?.nodes || []" :key="node.id" class="quest-journal__node" role="listitem"
        :class="{ 'quest-journal__node--map-related': node.id === selectedEntityId }">
        <span>{{ typeLabel(node.type) }}</span>
        <button type="button" :aria-pressed="selectedNode?.id === node.id" @click="selectedId = node.id">{{ node.label }}</button>
        <em v-if="node.verificationStatus">{{ verificationLabel(node.verificationStatus) }}</em>
        <span v-if="node.id === selectedEntityId">{{ t('worldInteraction.quest.selectedOnMap') }}</span>
      </div>
    </div>
    <section v-if="selectedNode" class="quest-journal__selection" :aria-label="t('worldInteraction.quest.journalDetail')">
      <h4>{{ selectedNode.label }}</h4>
      <button v-if="canLocateSelected" type="button" @click="$emit('locate', selectedNode.id)">
        {{ t('worldInteraction.decision.locateOnMap') }}
      </button>
      <ul v-if="connections.length">
        <li v-for="edge in connections" :key="edge.id">
          {{ edge.sourceLabel }} → {{ relationLabel(edge.type) }} → {{ edge.targetLabel }}
        </li>
      </ul>
      <p v-else>{{ t('worldInteraction.quest.noVisibleConnections') }}</p>
      <button type="button" @click="selectedId = null">{{ t('worldInteraction.quest.clearJournalSelection') }}</button>
    </section>
    <div v-if="journal?.unresolvedRefs.length" class="quest-journal__unresolved">
      <span v-for="item in journal.unresolvedRefs" :key="item.ref">
        {{ item.ref }} · {{ t(`worldInteraction.quest.unresolved.${item.reason}`) }}
      </span>
    </div>
  </details>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { QuestInteractionStatePayload } from '@/types/world'

const props = defineProps<{
  journal?: QuestInteractionStatePayload['questJournal']
  locatableEntityIds: string[]
  selectedEntityId?: string | null
}>()
defineEmits<{ locate: [entityId: string] }>()
const { t, te } = useI18n()
const selectedId = ref<string | null>(null)
const hasContent = computed(() => Boolean(props.journal?.nodes.length || props.journal?.unresolvedRefs.length))
const nodesById = computed(() => new Map((props.journal?.nodes || []).map(node => [node.id, node])))
const selectedNode = computed(() => selectedId.value ? nodesById.value.get(selectedId.value) : undefined)
const locatableIds = computed(() => new Set(props.locatableEntityIds))
const nonSpatialTypes = new Set(['quest', 'situation', 'goal', 'task', 'observation', 'fact', 'evidence', 'account', 'policy', 'control', 'quality_spec', 'process_pattern', 'case'])
const canLocateSelected = computed(() => Boolean(selectedNode.value
  && locatableIds.value.has(selectedNode.value.id) && !nonSpatialTypes.has(selectedNode.value.type)))
const connections = computed(() => (props.journal?.edges || [])
  .filter(edge => (edge.sourceId === selectedNode.value?.id || edge.targetId === selectedNode.value?.id)
    && nodesById.value.has(edge.sourceId) && nodesById.value.has(edge.targetId))
  .map(edge => ({ ...edge, sourceLabel: nodesById.value.get(edge.sourceId)!.label,
    targetLabel: nodesById.value.get(edge.targetId)!.label })))
const translatedOrRaw = (group: string, value: string) => {
  const key = `worldInteraction.quest.${group}.${value}`
  return te(key) ? t(key) : value
}
const typeLabel = (value: string) => translatedOrRaw('nodeType', value)
const relationLabel = (value: string) => translatedOrRaw('relationType', value)
const verificationLabel = (value: string) => translatedOrRaw('verification', value)
watch(() => props.journal, () => { selectedId.value = null })
</script>

<style scoped>
.quest-journal { margin-top: 10px; overflow-wrap: anywhere; }
summary { cursor: pointer; color: var(--el-color-primary); }
.quest-journal__graph, .quest-journal__unresolved { display: grid; gap: 6px; margin-top: 8px; }
.quest-journal__node { display: grid; grid-template-columns: minmax(72px, auto) minmax(0, 1fr) auto; gap: 8px; align-items: center; padding: 6px 8px; border-radius: 6px; background: color-mix(in srgb, var(--el-fill-color) 70%, transparent); }
.quest-journal__node--map-related { outline: 2px solid var(--el-color-primary); }
button { cursor: pointer; color: var(--el-color-primary); background: transparent; border: 1px solid var(--el-border-color); border-radius: 4px; padding: 4px 6px; text-align: left; overflow-wrap: anywhere; }
button[aria-pressed="true"] { font-weight: bold; border-color: var(--el-color-primary); }
button:focus-visible, summary:focus-visible { outline: 2px solid var(--el-color-primary); outline-offset: 2px; }
span, em { font-size: 12px; color: var(--el-text-color-secondary); font-style: normal; }
.quest-journal__selection { margin: 8px 0; padding: 8px; border: 1px solid var(--el-border-color); border-radius: 6px; }
h4 { margin: 0 0 8px; }
@media (max-width: 640px) { .quest-journal__node { grid-template-columns: minmax(0, 1fr); gap: 3px; } }
</style>
