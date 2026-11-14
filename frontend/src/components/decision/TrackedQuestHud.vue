<template>
      <article
        class="quest-token"
        :class="{ 'quest-token--foreground': foreground }"
        :aria-current="foreground ? 'true' : undefined"
      >
        <div class="quest-token__topline">
          <span class="quest-token__risk">{{ riskLabel(quest.riskLevel) }}</span>
          <span>{{ questStateLabel(quest.state) }}</span>
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
          <span>{{ clue.title }} · {{ verificationLabel(clue.verificationStatus) }}</span>
          <p>{{ clue.assertion }}</p>
          <el-button
            v-if="canManageClues && foreground"
            size="small"
            text
            :disabled="busy"
            @click="$emit('toggleClue', clue.id)"
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
              <span>{{ objectiveStateLabel(objective.state) }}</span>
              <span v-if="objective.id === quest.recommendedObjectiveId" class="quest-token__recommended">
                {{ t('worldInteraction.quest.recommended') }}
              </span>
              <el-button
                v-if="canFocus && objective.id !== quest.focusedObjectiveId"
                size="small"
                text
                :disabled="busy"
                @click="$emit('focus', quest.id, objective.id)"
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
            :disabled="busy"
            @click="$emit('untrack', quest.id)"
          >
            {{ t('worldInteraction.quest.untrack') }}
          </el-button>
        </div>
      </article>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { TrackedQuestSummary } from '@/types/world'
defineProps<{
  quest: TrackedQuestSummary; foreground: boolean; busy: boolean
  canFocus: boolean; canTrack: boolean; canManageClues: boolean
}>()
defineEmits<{
  locate: [entityId: string]; focus: [questId: string, objectiveId: string]
  untrack: [questId: string]; toggleClue: [clueId: string]
}>()
const { t, te } = useI18n()
const translated = (key: string, raw: string) => te(key) ? t(key) : raw
const riskLabel = (value: string) => translated(`worldInteraction.decision.riskLevel.${value}`, value)
const questStateLabel = (value: string) => translated(`worldInteraction.quest.state.${value}`, value)
const objectiveStateLabel = (value: string) => translated(`worldInteraction.quest.worldFeedback.objectiveState.${value}`, value)
const verificationLabel = (value: string) => translated(`worldInteraction.quest.verification.${value}`, value)
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

</script>

<style scoped>
.quest-token__topline, .quest-token__actions { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.quest-token h4 { margin: 2px 0; }
.quest-token__topline { color: var(--el-text-color-secondary); font-size: 11px; }
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

.quest-token p {
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


button:focus-visible { outline: 2px solid var(--el-color-primary); outline-offset: 2px; }
@media (max-width: 640px) {
  .quest-token__objective { grid-template-columns: minmax(0, 1fr) auto; }
  .quest-token__recommended, .quest-token__focused { grid-column: 1 / -1; }
}
</style>
