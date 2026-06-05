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
      <div
        ref="decisionFoldRef"
        class="decision-fold"
        :class="{
          'task-expanded': foldMode === 'maximized',
          'mode-split': foldMode === 'split',
          'is-resizing': isDragging,
        }"
      >
        <section
          class="task-zone fold-panel fold-panel--task"
          :class="{
            collapsed: foldMode === 'collapsed',
            'mode-split': foldMode === 'split',
            'mode-maximized': foldMode === 'maximized',
          }"
          :style="taskZoneStyle"
          role="region"
          :aria-labelledby="taskZoneTitleId"
        >
        <header :id="taskZoneTitleId" class="task-zone-header">
          <div class="zone-header-main">
            <span class="zone-title">{{ t('worldInteraction.decision.taskZoneTitle') }}</span>
            <span v-if="pendingBadgeCount > 0" class="zone-badge">{{ pendingBadgeCount }}</span>
          </div>
          <span class="zone-subtitle">{{ t('worldInteraction.decision.taskZoneSubtitle') }}</span>
        </header>

        <div v-show="showTaskBody" class="task-zone-body">
          <section
            v-if="decisionStore.focus"
            class="focus-summary"
            :class="`severity-stripe--${decisionStore.focus.severity}`"
          >
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
      </section>

      <div
        class="zone-divider fold-hinge"
        :class="{ 'fold-hinge--resizable': isResizable, 'fold-hinge--dragging': isDragging }"
        role="separator"
        aria-orientation="horizontal"
        :aria-label="hingeAriaLabel"
        :aria-valuenow="foldMode === 'split' ? Math.round(taskSplitRatio * 100) : undefined"
        tabindex="0"
        @pointerdown="onHingePointerDown"
        @keydown.enter.prevent="cycleFoldMode"
        @keydown.space.prevent="cycleFoldMode"
      >
        <span class="zone-divider-side zone-divider-hint">
          <template v-if="foldMode === 'collapsed'">{{ t('worldInteraction.decision.taskZoneCollapsedHint') }}</template>
        </span>
        <button
          type="button"
          class="decision-accent-btn decision-accent-btn--icon-only zone-divider-toggle"
          tabindex="-1"
          aria-hidden="true"
        >
          <el-icon :size="14">
            <ArrowUp v-if="foldMode !== 'collapsed'" />
            <ArrowDown v-else />
          </el-icon>
        </button>
        <span class="zone-divider-side zone-divider-side--end" aria-hidden="true" />
      </div>

      <div
        v-show="showConversation"
        class="conversation-zone fold-panel fold-panel--interaction"
        role="region"
        :aria-labelledby="conversationZoneTitleId"
      >
        <header :id="conversationZoneTitleId" class="conversation-zone-header">
          <span class="zone-title">{{ t('worldInteraction.decision.conversationZoneTitle') }}</span>
          <span class="zone-subtitle">{{ conversationZoneSubtitle }}</span>
        </header>
        <aico-thread-toolbar />
        <decision-conversation-thread ref="threadRef" />
      </div>
      </div>
    </div>

    <decision-query-box @submitted="onQuerySubmitted" />
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
import { useDecisionFoldLayout } from '@/composables/useDecisionFoldLayout'
import { useDecisionCenterStore } from '@/stores/decisionCenter'
import { useWorldSessionStore } from '@/stores/worldSession'

const { t } = useI18n()
const decisionStore = useDecisionCenterStore()
const worldSession = useWorldSessionStore()
const viewFilter = ref<'pending' | 'current'>('pending')
const hiddenEventIds = ref<Set<string>>(new Set())
const decisionFoldRef = ref<HTMLElement | null>(null)
const threadRef = ref<InstanceType<typeof DecisionConversationThread>>()

const {
  foldMode,
  taskSplitRatio,
  taskZoneStyle,
  showConversation,
  showTaskBody,
  isDragging,
  isResizable,
  collapseToHeader,
  cycleFoldMode,
  onHingePointerDown,
} = useDecisionFoldLayout(decisionFoldRef)

const taskZoneTitleId = 'decision-task-zone-title'
const conversationZoneTitleId = 'decision-conversation-zone-title'

const showPanelLoading = computed(
  () => worldSession.loading && !worldSession.interactionState,
)

const visibleEvents = computed(() => {
  if (viewFilter.value === 'current') return []
  return decisionStore.decisionEvents.filter(event => !hiddenEventIds.value.has(event.id))
})

const pendingBadgeCount = computed(() =>
  decisionStore.decisionEvents.filter(event => !hiddenEventIds.value.has(event.id)).length,
)

const conversationZoneSubtitle = computed(() =>
  worldSession.queryMode === 'aico'
    ? t('worldInteraction.decision.conversationZoneSubtitleAico')
    : t('worldInteraction.decision.conversationZoneSubtitleCommand'),
)

const hingeAriaLabel = computed(() => {
  if (foldMode.value === 'collapsed') return t('worldInteraction.decision.expandTaskZone')
  if (foldMode.value === 'split') return t('worldInteraction.decision.maximizeTaskZone')
  return t('worldInteraction.decision.collapseTaskZone')
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

async function onQuerySubmitted() {
  if (foldMode.value === 'maximized') {
    collapseToHeader()
  }
  await scrollConversationToBottom()
}

async function scrollConversationToBottom() {
  await nextTick()
  await threadRef.value?.scrollToBottom?.()
}
</script>

<style scoped>
.decision-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: var(--decision-pane-bg);
}

.region-menu {
  flex-shrink: 0;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
  background: var(--decision-pane-bg);
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
  padding: var(--spacing-xs) var(--spacing-sm) 0;
}

/* Flat foldable layout: upper task screen + hinge + lower interaction screen */
.decision-fold {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--decision-fold-border);
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  border-bottom: none;
  background: var(--decision-fold-bg);
}

.fold-panel--task {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--decision-fold-task-bg);
}

.task-zone.mode-split,
.task-zone.mode-maximized {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-bottom: 1px solid var(--decision-fold-border);
}

.task-zone.mode-split .task-zone-body,
.task-zone.mode-maximized .task-zone-body {
  flex: 1 1 0;
  min-height: 0;
  max-height: none;
  overflow-y: auto;
}

.fold-panel--interaction {
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--decision-fold-interaction-bg);
  font-size: var(--font-size-sm);
}

.task-zone-header,
.conversation-zone-header {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--decision-fold-border);
}

.task-zone-header {
  background: var(--decision-fold-task-header-bg);
  border-left: 3px solid rgba(64, 158, 255, 0.45);
}

.conversation-zone-header {
  background: var(--decision-fold-interaction-header-bg);
  margin-bottom: 0;
  border-left: 3px solid rgba(255, 255, 255, 0.12);
}

.zone-header-main {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.zone-title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

.zone-subtitle {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.zone-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--color-primary);
  color: #fff;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  line-height: 1;
}

.task-zone.collapsed .task-zone-header {
  border-bottom: none;
}

.task-zone-body {
  overflow-y: auto;
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  background: transparent;
}

.fold-hinge {
  flex-shrink: 0;
  position: relative;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  min-height: var(--decision-fold-hinge-height);
  padding: 0 var(--spacing-sm);
  margin: 0;
  touch-action: none;
  background: linear-gradient(
    180deg,
    var(--decision-fold-hinge-top) 0%,
    var(--decision-fold-hinge-mid) 50%,
    var(--decision-fold-hinge-bottom) 100%
  );
  border-top: 1px solid var(--decision-fold-hinge-line);
  border-bottom: none;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.fold-hinge--resizable {
  cursor: row-resize;
}

.fold-hinge--dragging,
.decision-fold.is-resizing {
  user-select: none;
}

.fold-hinge:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

.fold-hinge::before {
  content: '';
  position: absolute;
  left: 12%;
  right: 12%;
  top: 50%;
  height: 1px;
  background: var(--decision-fold-hinge-line);
  pointer-events: none;
  opacity: 0.7;
}

.zone-divider-side {
  min-width: 0;
}

.zone-divider-hint {
  grid-column: 1;
  justify-self: start;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.zone-divider-toggle {
  grid-column: 2;
  justify-self: center;
  position: relative;
  z-index: 1;
  width: var(--decision-fold-hinge-btn-size);
  min-width: var(--decision-fold-hinge-btn-size);
  height: var(--decision-fold-hinge-btn-size);
  border-radius: 999px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.22);
  pointer-events: none;
}

.zone-divider-toggle :deep(.el-icon) {
  font-size: 14px;
}

.decision-fold.task-expanded .fold-hinge {
  border-bottom: 1px solid var(--decision-fold-hinge-line);
}

.conversation-zone {
  flex: 1 1 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0 var(--spacing-md) var(--spacing-md);
  border-top: 1px solid var(--decision-fold-border);
}

.conversation-zone-header {
  padding: var(--spacing-sm) 0;
  margin-bottom: 0;
  border-bottom: 1px solid var(--decision-fold-border);
}

.focus-summary,
.next-action,
.error-card {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--decision-card-bg);
  padding: var(--spacing-lg);
  border-left-width: var(--decision-severity-stripe-width);
  border-left-style: solid;
}

.focus-summary.severity-stripe--info,
.next-action {
  border-left-color: var(--decision-severity-info);
}

.focus-summary.severity-stripe--warning {
  border-left-color: var(--decision-severity-warning);
}

.focus-summary.severity-stripe--critical {
  border-left-color: var(--decision-severity-critical);
}

.focus-summary.severity-stripe--normal {
  border-left-color: var(--decision-severity-normal);
}

.focus-summary h3 {
  margin: var(--spacing-xs) 0;
  font-size: var(--decision-focus-title-size);
}

.focus-summary p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
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
  border-left-color: var(--color-primary);
}

.next-action.clickable {
  cursor: pointer;
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.next-action.clickable:hover {
  border-color: var(--color-primary);
  background: rgba(64, 158, 255, 0.06);
}

.error-card {
  border-color: rgba(245, 108, 108, 0.35);
  border-left-color: var(--color-danger);
  color: var(--color-danger);
}
</style>
