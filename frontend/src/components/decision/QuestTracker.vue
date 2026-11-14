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

    <section v-if="canManagePulse && visiblePulse.length" class="world-pulse" aria-labelledby="world-pulse-title">
      <h4 id="world-pulse-title">{{ t('worldInteraction.quest.worldPulse.title') }}</h4>
      <article v-for="item in visiblePulse" :key="item.id" class="world-pulse__item">
        <div>
          <strong>{{ riskLabel(item.severity) }}</strong>
          <span>{{ t(`worldInteraction.quest.worldPulse.attention.${item.attention}`) }}</span>
          <p>{{ item.assertion }}</p>
        </div>
        <div class="world-pulse__actions">
          <el-button
            v-if="item.attention === 'new'"
            size="small"
            text
            :disabled="worldSession.sessionActionBusy"
            @click="setPulseAttention(item.situationId, 'seen')"
          >{{ t('worldInteraction.quest.worldPulse.markSeen') }}</el-button>
          <el-button
            v-if="item.attention === 'snoozed'"
            size="small"
            text
            :disabled="worldSession.sessionActionBusy"
            @click="setPulseAttention(item.situationId, 'reset')"
          >{{ t('worldInteraction.quest.worldPulse.showNow') }}</el-button>
          <el-button
            v-else
            size="small"
            text
            :disabled="worldSession.sessionActionBusy"
            @click="snoozePulse(item.situationId)"
          >{{ t('worldInteraction.quest.worldPulse.snooze') }}</el-button>
          <el-button
            size="small"
            text
            :disabled="worldSession.sessionActionBusy"
            @click="setPulseAttention(item.situationId, 'ui_dismissed')"
          >{{ t('worldInteraction.quest.worldPulse.dismiss') }}</el-button>
        </div>
      </article>
    </section>

    <section v-if="visibleFeedback.length" class="world-feedback" aria-labelledby="world-feedback-title">
      <h4 id="world-feedback-title">{{ t('worldInteraction.quest.worldFeedback.title') }}</h4>
      <ol role="log" aria-live="polite" aria-relevant="additions text">
        <li v-for="item in visibleFeedback" :key="item.id">
          <span>{{ t(`worldInteraction.quest.worldFeedback.actor.${item.actorKind}`) }}</span>
          <strong>{{ item.summary }}<template v-if="item.objectiveState"> → {{ objectiveStateLabel(item.objectiveState) }}</template></strong>
          <span>{{ t(`worldInteraction.quest.worldFeedback.status.${item.status}`) }}</span>
        </li>
      </ol>
    </section>

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
      <article
        v-for="quest in questState.trackedQuests"
        :key="quest.id"
        class="quest-token"
        :class="{ 'quest-token--foreground': quest.id === questState.foregroundQuestId }"
        :aria-current="quest.id === questState.foregroundQuestId ? 'true' : undefined"
      >
        <div class="quest-token__topline">
          <span class="quest-token__risk">{{ riskLabel(quest.riskLevel) }}</span>
          <span>{{ quest.state }}</span>
        </div>
        <h4>{{ quest.title }}</h4>
        <p v-if="quest.situation?.assertion">{{ quest.situation.assertion }}</p>
        <p v-if="quest.companion" class="quest-token__companion">
          {{ t('worldInteraction.quest.companion', { name: quest.companion.name, role: quest.companion.role }) }}
        </p>
        <p v-else-if="quest.companionFallback === 'aico'" class="quest-token__companion">
          {{ t('worldInteraction.quest.aicoFallback') }}
        </p>
        <div v-if="mapRefs(quest).length" class="quest-token__map-refs">
          <button
            v-for="ref in mapRefs(quest)"
            :key="`${quest.id}:${ref.id}`"
            type="button"
            @click="$emit('locate', ref.id)"
          >
            {{ t('worldInteraction.quest.locateRef', { kind: t(`worldInteraction.quest.mapRefKind.${ref.kind}`), id: ref.id }) }}
          </button>
        </div>
        <div v-for="clue in quest.clues || []" :key="clue.id" class="quest-token__clue">
          <span>{{ clue.title }} · {{ clue.verificationStatus }}</span>
          <p>{{ clue.assertion }}</p>
          <el-button
            v-if="canManageClues && quest.id === questState.foregroundQuestId"
            size="small"
            text
            :disabled="worldSession.sessionActionBusy"
            @click="toggleCluePin(clue.id)"
          >
            {{ clue.pinned ? t('worldInteraction.quest.unpinClue') : t('worldInteraction.quest.pinClue') }}
          </el-button>
        </div>
        <div
          class="quest-token__progress"
          role="progressbar"
          :aria-label="t('worldInteraction.quest.progressLabel', { title: quest.title })"
          :aria-valuenow="quest.progress?.percent || 0"
          aria-valuemin="0"
          aria-valuemax="100"
        >
          <span :style="{ width: `${quest.progress?.percent || 0}%` }" />
        </div>
        <div class="quest-token__actions">
          <div v-if="quest.objectives.length" class="quest-token__objectives">
            <span>{{ t('worldInteraction.quest.objectives') }}</span>
            <div
              v-for="objective in quest.objectives"
              :key="objective.id"
              class="quest-token__objective"
              :class="{ 'quest-token__objective--recommended': objective.id === quest.recommendedObjectiveId }"
            >
              <strong>{{ objective.title }}</strong>
              <span>{{ objective.state }}</span>
              <span v-if="objective.id === quest.recommendedObjectiveId" class="quest-token__recommended">
                {{ t('worldInteraction.quest.recommended') }}
              </span>
              <el-button
                v-if="canFocus && objective.id !== quest.focusedObjectiveId"
                size="small"
                text
                :disabled="worldSession.sessionActionBusy"
                @click="focusRecommended(quest.id, objective.id)"
              >
                {{ t('worldInteraction.quest.focusObjective') }}
              </el-button>
              <span v-else-if="objective.id === quest.focusedObjectiveId" class="quest-token__focused">
                {{ t('worldInteraction.quest.currentFocus') }}
              </span>
            </div>
          </div>
          <el-button
            v-if="canTrack"
            size="small"
            text
            :disabled="worldSession.sessionActionBusy"
            @click="untrackQuest(quest.id)"
          >
            {{ t('worldInteraction.quest.untrack') }}
          </el-button>
        </div>
      </article>
    </div>
    <p v-else class="quest-tracker__empty">{{ t('worldInteraction.quest.empty') }}</p>

    <details v-if="canViewJournal && journalHasContent" class="quest-journal">
      <summary>{{ t('worldInteraction.quest.journal') }}</summary>
      <div class="quest-journal__graph" role="list">
        <div v-for="node in questState.questJournal?.nodes || []" :key="node.id" class="quest-journal__node" role="listitem">
          <span>{{ node.type }}</span>
          <strong>{{ node.label }}</strong>
          <em v-if="node.verificationStatus">{{ node.verificationStatus }}</em>
        </div>
      </div>
      <div v-if="questState.questJournal?.unresolvedRefs.length" class="quest-journal__unresolved">
        <span v-for="item in questState.questJournal.unresolvedRefs" :key="item.ref">
          {{ item.ref }} · {{ t(`worldInteraction.quest.unresolved.${item.reason}`) }}
        </span>
      </div>
    </details>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useWorldSessionStore } from '@/stores/worldSession'
import type { TrackedQuestSummary } from '@/types/world'

const { t } = useI18n()
defineEmits<{ locate: [entityId: string] }>()
const worldSession = useWorldSessionStore()
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
const journalHasContent = computed(() =>
  Boolean(
    questState.value?.questJournal?.nodes.length
      || questState.value?.questJournal?.unresolvedRefs.length,
  ),
)
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

const riskLabel = (riskLevel: string) => t(`worldInteraction.decision.riskLevel.${riskLevel}`)
const objectiveStateLabel = (state: string) => {
  const key = `worldInteraction.quest.worldFeedback.objectiveState.${state}`
  const translated = t(key)
  return translated === key ? state : translated
}
</script>

<style scoped>
.quest-tracker {
  border: 1px solid color-mix(in srgb, var(--el-color-primary) 28%, transparent);
  border-radius: 12px;
  padding: 12px;
  background: linear-gradient(145deg, color-mix(in srgb, var(--el-color-primary) 8%, transparent), transparent 65%);
}

.quest-tracker__header,
.quest-token__topline,
.quest-token__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.quest-tracker__header h3,
.quest-token h4 {
  margin: 2px 0;
}

.quest-tracker__eyebrow,
.quest-tracker__revision,
.quest-token__topline,
.quest-journal__node span,
.quest-journal__node em {
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

.world-pulse {
  display: grid;
  gap: 8px;
  margin-top: 10px;
}

.world-pulse h4 {
  margin: 0;
}

.world-pulse__item {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding: 8px;
  border-left: 3px solid var(--el-color-warning);
  border-radius: 6px;
  background: color-mix(in srgb, var(--el-color-warning) 7%, transparent);
}

.world-pulse__item p {
  margin: 4px 0 0;
}

.world-pulse__item span {
  margin-left: 8px;
  color: var(--el-text-color-secondary);
}

.world-pulse__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
}

.world-feedback {
  margin-top: 10px;
}

.world-feedback h4 {
  margin: 0 0 6px;
}

.world-feedback ol {
  display: grid;
  gap: 5px;
  margin: 0;
  padding-left: 22px;
}

.world-feedback li {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: baseline;
  color: var(--el-text-color-regular);
  font-size: 12px;
}

.quest-token {
  padding: 10px;
  border-left: 3px solid var(--el-border-color);
  border-radius: 8px;
  background: color-mix(in srgb, var(--el-bg-color) 88%, transparent);
}

.quest-token--foreground {
  border-left-color: var(--el-color-primary);
  box-shadow: 0 0 18px color-mix(in srgb, var(--el-color-primary) 12%, transparent);
}

.quest-token p,
.quest-tracker__empty {
  margin: 6px 0;
  color: var(--el-text-color-regular);
  font-size: 13px;
}

.quest-token__map-refs,
.quest-token__objectives,
.quest-token__clue {
  display: grid;
  gap: 5px;
  margin-top: 8px;
}

.quest-token__map-refs {
  display: flex;
  flex-wrap: wrap;
}

.quest-token__map-refs button {
  border: 0;
  padding: 3px 6px;
  color: var(--el-color-primary);
  background: transparent;
  cursor: pointer;
}

.quest-token__objective {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 6px;
  align-items: center;
  padding: 5px 7px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--el-fill-color) 70%, transparent);
}

.quest-token__objective--recommended {
  outline: 1px solid color-mix(in srgb, var(--el-color-primary) 45%, transparent);
}

.quest-token__recommended,
.quest-token__focused {
  color: var(--el-color-primary);
  font-size: 11px;
}

.quest-token__clue {
  padding: 7px;
  border-left: 2px solid var(--el-color-primary);
  background: color-mix(in srgb, var(--el-fill-color) 70%, transparent);
}

.quest-token__clue p {
  margin: 0;
}

.quest-token__progress {
  height: 3px;
  overflow: hidden;
  border-radius: 99px;
  background: var(--el-border-color-lighter);
}

.quest-token__progress span {
  display: block;
  height: 100%;
  background: var(--el-color-primary);
}

.quest-journal {
  margin-top: 10px;
}

.quest-journal summary {
  cursor: pointer;
  color: var(--el-color-primary);
}

.quest-journal__graph,
.quest-journal__unresolved {
  display: grid;
  gap: 6px;
  margin-top: 8px;
}

.quest-journal__node {
  display: grid;
  grid-template-columns: minmax(72px, auto) 1fr auto;
  gap: 8px;
  align-items: center;
  padding: 6px 8px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--el-fill-color) 70%, transparent);
}

.quest-journal__unresolved span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

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

  .quest-token__objective {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .quest-token__recommended,
  .quest-token__focused {
    grid-column: 1 / -1;
  }

  .quest-journal__node {
    grid-template-columns: minmax(0, 1fr);
    gap: 3px;
  }

  .world-pulse__item {
    flex-direction: column;
  }
}

@media (prefers-reduced-motion: reduce) {
  .quest-tracker *,
  .quest-tracker *::before,
  .quest-tracker *::after {
    scroll-behavior: auto !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
</style>
