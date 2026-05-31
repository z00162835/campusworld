<template>
  <section class="decision-panel">
    <div class="region-menu">
      <h2>{{ t('worldInteraction.decision.title') }}</h2>
      <div class="region-actions">
        <el-button size="small" text :type="viewFilter === 'pending' ? 'primary' : undefined" @click="viewFilter = 'pending'">
          {{ t('worldInteraction.decision.pending') }}
        </el-button>
        <el-button size="small" text :type="viewFilter === 'current' ? 'primary' : undefined" @click="viewFilter = 'current'">
          {{ t('worldInteraction.decision.currentTask') }}
        </el-button>
        <el-button size="small" text @click="clearResolved">
          {{ t('worldInteraction.decision.clearResolved') }}
        </el-button>
      </div>
    </div>

    <div class="decision-scroll">
      <div v-if="worldSession.loading" class="focus-summary">{{ t('worldInteraction.decision.loading') }}</div>
      <div v-else-if="worldSession.error" class="error-card">
        <p>{{ worldSession.error }}</p>
        <el-button size="small" @click="worldSession.loadCurrent">{{ t('common.retry') }}</el-button>
      </div>

      <section v-if="decisionStore.focus" class="focus-summary">
        <div class="severity">{{ decisionStore.focus.severity }}</div>
        <h3>{{ decisionStore.focus.title }}</h3>
        <p>{{ decisionStore.focus.summary }}</p>
      </section>

      <decision-event-card
        v-for="event in visibleEvents"
        :key="event.id"
        :event="event"
        @execute="executeAction"
      />

      <active-task-card
        v-if="decisionStore.activeTask && viewFilter !== 'pending'"
        :task="decisionStore.activeTask"
        @execute="executeTaskAction"
      />

      <section
        v-if="decisionStore.nextBestAction && viewFilter !== 'pending'"
        class="next-action clickable"
        role="button"
        tabindex="0"
        @click="runNextBestAction"
        @keyup.enter="runNextBestAction"
      >
        <span>{{ t('worldInteraction.decision.nextBestAction') }}</span>
        <strong>{{ decisionStore.nextBestAction.label }}</strong>
      </section>

      <quick-query-chips
        :queries="decisionStore.quickQueries"
        @query="worldSession.submitQuery"
      />

      <div class="query-results">
        <article v-for="card in worldSession.queryCards" :key="card.id" class="query-card">
          <span>{{ card.mode }}</span>
          <h4>{{ card.title }}</h4>
          <p>{{ card.answer }}</p>
        </article>
      </div>
    </div>

    <decision-query-box />
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import DecisionEventCard from './DecisionEventCard.vue'
import ActiveTaskCard from './ActiveTaskCard.vue'
import QuickQueryChips from './QuickQueryChips.vue'
import DecisionQueryBox from './DecisionQueryBox.vue'
import { useDecisionCenterStore } from '@/stores/decisionCenter'
import { useWorldSessionStore } from '@/stores/worldSession'

const { t } = useI18n()
const decisionStore = useDecisionCenterStore()
const worldSession = useWorldSessionStore()
const viewFilter = ref<'pending' | 'current'>('pending')
const hiddenEventIds = ref<Set<string>>(new Set())

const visibleEvents = computed(() => {
  if (viewFilter.value === 'current') return []
  return decisionStore.decisionEvents.filter(event => !hiddenEventIds.value.has(event.id))
})

const executeAction = async (eventId: string, optionId: string) => {
  await decisionStore.executeDecisionOption(eventId, optionId)
}

const executeTaskAction = async (optionId: string) => {
  const task = decisionStore.activeTask
  if (!task) return
  await decisionStore.executeDecisionOption(task.id, optionId)
}

const runNextBestAction = async () => {
  const action = decisionStore.nextBestAction
  if (!action) return
  const eventId = decisionStore.activeTask?.id || visibleEvents.value[0]?.id
  if (!eventId) return
  await decisionStore.executeDecisionOption(eventId, action.id)
}

function clearResolved() {
  hiddenEventIds.value = new Set(decisionStore.decisionEvents.map(event => event.id))
}
</script>

<style scoped>
.decision-panel {
  display: flex;
  flex-direction: column;
  min-height: 620px;
}

.region-menu {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
}

.region-menu h2 {
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
}

.region-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.decision-scroll {
  flex: 1;
  overflow: auto;
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.focus-summary,
.next-action,
.query-card,
.error-card {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: #1b1f26;
  padding: var(--spacing-lg);
}

.focus-summary h3,
.query-card h4 {
  margin: var(--spacing-xs) 0;
  font-size: var(--font-size-lg);
}

.focus-summary p,
.query-card p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.55;
}

.severity,
.query-card span,
.next-action span {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  text-transform: uppercase;
}

.next-action {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.next-action.clickable {
  cursor: pointer;
}

.next-action.clickable:hover {
  border-color: var(--color-primary);
}

.error-card {
  border-color: rgba(245, 108, 108, 0.35);
  color: var(--color-danger);
}

@media (max-width: 980px) {
  .decision-panel {
    min-height: 520px;
  }
}
</style>
