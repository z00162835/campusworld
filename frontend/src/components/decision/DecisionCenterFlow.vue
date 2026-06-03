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

    <div v-if="showPanelLoading" class="panel-loading">{{ t('worldInteraction.decision.loading') }}</div>
    <div v-else-if="worldSession.error" class="error-card panel-loading">
      <p>{{ worldSession.error }}</p>
      <el-button size="small" @click="worldSession.loadCurrent">{{ t('common.retry') }}</el-button>
    </div>

    <div v-else class="decision-body">
      <div v-show="!taskZoneCollapsed" class="task-zone">
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
          v-if="decisionStore.activeTask"
          :task="decisionStore.activeTask"
          @execute="executeTaskAction"
        />

        <section
          v-if="decisionStore.nextBestAction"
          class="next-action clickable"
          role="button"
          tabindex="0"
          @click="runNextBestAction"
          @keyup.enter="runNextBestAction"
        >
          <span>{{ t('worldInteraction.decision.nextBestAction') }}</span>
          <strong>{{ decisionStore.nextBestAction.label }}</strong>
        </section>
      </div>

      <div class="task-zone-handle">
        <button
          type="button"
          class="task-zone-toggle"
          :aria-label="taskZoneCollapsed ? t('worldInteraction.decision.expandTaskZone') : t('worldInteraction.decision.collapseTaskZone')"
          :title="taskZoneCollapsed ? t('worldInteraction.decision.expandTaskZone') : t('worldInteraction.decision.collapseTaskZone')"
          @click="taskZoneCollapsed = !taskZoneCollapsed"
        >
          <el-icon :size="14">
            <ArrowUp v-if="!taskZoneCollapsed" />
            <ArrowDown v-else />
          </el-icon>
        </button>
      </div>

      <div ref="conversationZoneRef" class="conversation-zone">
        <aico-thread-toolbar />
        <decision-conversation-thread ref="threadRef" />
      </div>
    </div>

    <decision-query-box @submitted="scrollConversationToBottom" />
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import DecisionEventCard from './DecisionEventCard.vue'
import ActiveTaskCard from './ActiveTaskCard.vue'
import DecisionQueryBox from './DecisionQueryBox.vue'
import DecisionConversationThread from './DecisionConversationThread.vue'
import AicoThreadToolbar from './AicoThreadToolbar.vue'
import { useDecisionCenterStore } from '@/stores/decisionCenter'
import { useWorldSessionStore } from '@/stores/worldSession'

const { t } = useI18n()
const decisionStore = useDecisionCenterStore()
const worldSession = useWorldSessionStore()
const viewFilter = ref<'pending' | 'current'>('pending')
const taskZoneCollapsed = ref(false)
const hiddenEventIds = ref<Set<string>>(new Set())
const conversationZoneRef = ref<HTMLElement>()
const threadRef = ref<InstanceType<typeof DecisionConversationThread>>()

const showPanelLoading = computed(
  () => worldSession.loading && !worldSession.interactionState,
)

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

async function scrollConversationToBottom() {
  await nextTick()
  await threadRef.value?.scrollToBottom()
  const zone = conversationZoneRef.value
  if (zone) zone.scrollTop = zone.scrollHeight
}
</script>

<style scoped>
.decision-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.region-menu {
  flex-shrink: 0;
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

.panel-loading {
  padding: var(--spacing-lg);
  flex-shrink: 0;
}

.decision-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.task-zone {
  flex-shrink: 0;
  max-height: 40vh;
  overflow-y: auto;
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  background: #15181d;
}

.task-zone-handle {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2px 0;
  background: #15181d;
  border-top: 1px solid var(--border-color);
  border-bottom: 1px solid var(--border-color);
}

.task-zone-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 22px;
  padding: 0;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: #1b1f26;
  color: var(--text-secondary);
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease, background 0.15s ease;
}

.task-zone-toggle:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: #20252d;
}

.task-zone-toggle:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.conversation-zone {
  flex: 1 1 0;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: var(--spacing-lg);
  background: #13161b;
  display: flex;
  flex-direction: column;
}

.focus-summary,
.next-action,
.error-card {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: #1b1f26;
  padding: var(--spacing-lg);
}

.focus-summary h3 {
  margin: var(--spacing-xs) 0;
  font-size: var(--font-size-lg);
}

.focus-summary p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.55;
}

.severity,
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
</style>
