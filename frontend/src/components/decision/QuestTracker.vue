<template>
  <section v-if="questState" class="quest-tracker" aria-labelledby="quest-tracker-title">
    <header class="quest-tracker__header">
      <div>
        <span class="quest-tracker__eyebrow">{{ t('worldInteraction.quest.eyebrow') }}</span>
        <h3 id="quest-tracker-title">{{ t('worldInteraction.quest.title') }}</h3>
      </div>
      <span class="quest-tracker__revision">r{{ questState.projectionRevision }}</span>
    </header>
    <p class="sr-only" role="status" aria-live="polite" aria-atomic="true">
      {{ foregroundAnnouncement }}
    </p>

    <WorldPulse
      v-if="canManagePulse"
      :items="visiblePulse"
      :busy="worldSession.sessionActionBusy"
      @attention="setPulseAttention"
      @snooze="snoozePulse"
    />

    <WorldFeedback :items="visibleFeedback" />

    <button
      v-if="canTrack && trackableTaskQuestId"
      type="button"
      class="quest-tracker__callout"
      :disabled="worldSession.sessionActionBusy"
      @click="trackActiveQuest"
    >
      <span>{{ t('worldInteraction.quest.discovered') }}</span>
      <strong>{{ activeTask?.questTitle || activeTask?.title }}</strong>
      <em>{{ t('worldInteraction.quest.track') }}</em>
    </button>

    <div v-if="questState.trackedQuests.length" class="quest-tracker__list">
      <TrackedQuestHud
        v-for="quest in questState.trackedQuests" :key="quest.id"
        :quest="quest" :foreground="quest.id === questState.foregroundQuestId"
        :busy="worldSession.sessionActionBusy"
        :can-focus="canFocus" :can-track="canTrack" :can-manage-clues="canManageClues"
        @locate="$emit('locate', $event)" @focus="focusRecommended"
        @untrack="untrackQuest" @toggle-clue="toggleCluePin"
      />
    </div>
    <p v-else class="quest-tracker__empty">{{ t('worldInteraction.quest.empty') }}</p>

    <QuestCompanion
      v-if="worldSession.foregroundQuest && activeTask?.questId !== worldSession.foregroundQuest.id"
      :companion-name="worldSession.foregroundQuest.companion?.name"
      :busy="worldSession.sessionActionBusy"
      @ask="$emit('ask', $event)"
    />

    <QuestJournal
      v-if="canViewJournal"
      :journal="questState.questJournal"
      :locatable-entity-ids="journalMapRefs"
      :selected-entity-id="worldMap.selectedInspect?.entityId"
      @locate="$emit('locate', $event)"
    />
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useWorldSessionStore } from '@/stores/worldSession'
import type { TrackedQuestSummary } from '@/types/world'
import WorldFeedback from './WorldFeedback.vue'
import WorldPulse from './WorldPulse.vue'
import TrackedQuestHud from './TrackedQuestHud.vue'
import QuestJournal from './QuestJournal.vue'
import QuestCompanion from './QuestCompanion.vue'
import { useWorldMapStore } from '@/stores/worldMap'

const { t } = useI18n()
defineEmits<{ locate: [entityId: string]; ask: [intent: 'next_step' | 'explain_basis'] }>()
const worldSession = useWorldSessionStore()
const worldMap = useWorldMapStore()
const questState = computed(() => worldSession.questInteraction)
const activeTask = computed(() => worldSession.decisionCenter?.activeTask || null)
const trackedIds = computed(() => new Set(questState.value?.trackedQuests.map(quest => quest.id) || []))
const hasCapability = (capability: string) => questState.value?.capabilities.some(item => item === capability) === true
const canTrack = computed(() => hasCapability('multi_quest_tracking'))
const canFocus = computed(() => hasCapability('durable_focus'))
const canViewJournal = computed(() => hasCapability('quest_graph'))
const canManageClues = computed(() => hasCapability('observation_clues'))
const canManagePulse = computed(() => hasCapability('situation_attention'))
const visiblePulse = computed(() => (questState.value?.worldPulse || []).filter(item => item.attention !== 'ui_dismissed'))
const visibleFeedback = computed(() => (questState.value?.worldFeedback || []).slice(0, 8))
const trackableTaskQuestId = computed(() => {
  const questId = activeTask.value?.questId
  return questId && !trackedIds.value.has(questId) ? questId : null
})
const foregroundAnnouncement = computed(() => {
  const quest = questState.value?.trackedQuests.find(item => item.id === questState.value?.foregroundQuestId)
  return quest ? t('worldInteraction.quest.foregroundAnnouncement', { title: quest.title }) : ''
})

const trackActiveQuest = () => {
  if (!trackableTaskQuestId.value) return
  return worldSession.executeQuestInteractionAction({ action: 'track', questId: trackableTaskQuestId.value })
}

const untrackQuest = (questId: string) =>
  worldSession.executeQuestInteractionAction({ action: 'untrack', questId })

const focusRecommended = (questId: string, objectiveId: string) =>
  worldSession.executeQuestInteractionAction({ action: 'focus_objective', questId, objectiveId })

const isCluePinned = (clueNodeId: string) =>
  questState.value?.questJournal?.edges.some(
    edge => edge.type === 'PINS_CLUE' && edge.targetId === clueNodeId,
  ) === true

const toggleCluePin = (clueNodeId: string) => {
  const questId = questState.value?.foregroundQuestId
  if (!questId) return
  return worldSession.executeQuestInteractionAction({
    action: isCluePinned(clueNodeId) ? 'unpin_clue' : 'pin_clue',
    questId,
    clueNodeId,
  })
}

const setPulseAttention = (situationId: string, attention: 'seen' | 'snoozed' | 'ui_dismissed' | 'reset') =>
  worldSession.executeQuestInteractionAction({ action: 'situation_attention', situationId, attention })

const snoozePulse = (situationId: string) =>
  worldSession.executeQuestInteractionAction({
    action: 'situation_attention',
    situationId,
    attention: 'snoozed',
    snoozedUntil: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
  })

const mapRefs = (quest: TrackedQuestSummary) => {
  const situation = quest.situation
  if (!situation) return []
  const refs = [
    ...(situation.primarySubjectRef ? [{ id: situation.primarySubjectRef, kind: 'primary' }] : []),
    ...(situation.relatedEntityRefs || []).map(id => ({ id, kind: 'related' })),
    ...(situation.scopedAtRef ? [{ id: situation.scopedAtRef, kind: 'scope' }] : []),
  ]
  return refs.filter((ref, index) => refs.findIndex(item => item.id === ref.id) === index)
}

const journalMapRefs = computed(() => {
  const quest = questState.value?.trackedQuests.find(item => item.id === questState.value?.foregroundQuestId)
  return quest ? mapRefs(quest).map(ref => ref.id) : []
})

</script>

<style scoped>
.quest-tracker {
  border: 1px solid color-mix(in srgb, var(--el-color-primary) 28%, transparent);
  border-radius: 12px;
  padding: 12px;
  background: linear-gradient(145deg, color-mix(in srgb, var(--el-color-primary) 8%, transparent), transparent 65%);
}

.quest-tracker__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.quest-tracker__header h3 {
  margin: 2px 0;
}

.quest-tracker__eyebrow,
.quest-tracker__revision {
  color: var(--el-text-color-secondary);
  font-size: 11px;
  font-style: normal;
  text-transform: uppercase;
}

.quest-tracker__callout {
  display: grid;
  width: 100%;
  margin-top: 10px;
  padding: 10px;
  border: 1px dashed var(--el-color-primary);
  border-radius: 10px;
  color: inherit;
  text-align: left;
  background: transparent;
  cursor: pointer;
}

.quest-tracker__callout em {
  color: var(--el-color-primary);
  font-style: normal;
}

.quest-tracker__list {
  display: grid;
  gap: 8px;
  margin-top: 10px;
}

.quest-tracker__empty { margin: 6px 0; color: var(--el-text-color-regular); font-size: 13px; }

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 640px) {
  .quest-tracker {
    padding: 8px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .quest-tracker :deep(*),
  .quest-tracker :deep(*::before),
  .quest-tracker :deep(*::after) {
    scroll-behavior: auto !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
</style>
