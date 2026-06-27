<template>
  <aside class="context-panel">
    <div class="region-menu">
      <h2 class="region-menu-title">
        <app-icon name="context" :size="18" />
        <span>{{ t('worldInteraction.context.title') }}</span>
      </h2>
      <button
        type="button"
        class="pane-icon-btn"
        :title="t('worldInteraction.context.collapse')"
        :aria-label="t('worldInteraction.context.collapse')"
        @click="$emit('collapse')"
      >
        <app-icon name="chevronRight" :size="16" />
      </button>
    </div>

    <div v-if="worldSession.loading" class="empty">{{ t('worldInteraction.context.loading') }}</div>
    <div v-else-if="loadError" class="empty error">
      <p>{{ loadError }}</p>
      <el-button size="small" @click="worldSession.loadCurrent">{{ t('common.retry') }}</el-button>
    </div>
    <div v-else-if="!summary" class="empty">{{ t('worldInteraction.context.noData') }}</div>
    <div v-else class="summary-body">
      <section>
        <span>{{ t('worldInteraction.context.currentLocation') }}</span>
        <h3>{{ summary.currentSpace.name }}</h3>
        <p>{{ summary.currentSpace.oneLineSummary }}</p>
      </section>

      <section v-if="summary.activeTask">
        <span>{{ t('worldInteraction.context.currentTask') }}</span>
        <h3>{{ summary.activeTask.title }}</h3>
        <p>{{ summary.activeTask.currentStep }}</p>
        <el-progress :percentage="summary.activeTask.progress" :show-text="false" />
      </section>

      <section v-if="summary.lastHandledTask">
        <span>{{ t('worldInteraction.context.lastHandledTask') }}</span>
        <h3>{{ summary.lastHandledTask.title }}</h3>
        <p>{{ lastHandledLabel }}</p>
      </section>

      <section>
        <span>{{ t('worldInteraction.context.pendingCount', { count: summary.pendingDecisionCount }) }}</span>
      </section>

      <section>
        <span>{{ t('worldInteraction.context.nearbyAgents') }}</span>
        <div v-if="summary.nearbyAgents.highlighted.length" class="agent-list">
          <div v-for="agent in summary.nearbyAgents.highlighted" :key="agent.id" class="agent-row">
            <strong>{{ agent.name }}</strong>
            <small>{{ agent.role }} · {{ agent.status }}</small>
          </div>
        </div>
        <p v-else>{{ t('worldInteraction.context.noAgents') }}</p>
      </section>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/common/AppIcon.vue'
import { useWorldSessionStore } from '@/stores/worldSession'

defineEmits<{ collapse: [] }>()

const { t } = useI18n()
const worldSession = useWorldSessionStore()
const summary = computed(() => worldSession.contextSummary)
const loadError = computed(() => worldSession.error || (worldSession.errorKey ? t(worldSession.errorKey) : ''))

const lastHandledLabel = computed(() => {
  const task = summary.value?.lastHandledTask
  if (!task) return ''
  const when = task.handledAt ? new Date(task.handledAt).toLocaleString() : ''
  return t('worldInteraction.context.lastHandledDetail', { status: task.status, when })
})
</script>

<style scoped>
.context-panel {
  min-height: 360px;
  flex: 1;
}

.region-menu {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
}

.region-menu h2,
.region-menu-title {
  margin: 0;
  font-size: var(--font-size-base);
}

.region-menu-title {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-sm);
  min-width: 0;
  font-weight: var(--font-weight-semibold);
}

.pane-icon-btn {
  border: 0;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: var(--spacing-xs);
  border-radius: var(--radius-md);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.pane-icon-btn:hover {
  color: var(--text-secondary);
  background: var(--bg-hover);
}

.pane-icon-btn:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.summary-body {
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

section {
  border-bottom: 1px solid var(--border-color-light);
  padding-bottom: var(--spacing-lg);
}

section:last-child {
  border-bottom: 0;
}

span {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  text-transform: uppercase;
}

h3 {
  margin: var(--spacing-xs) 0;
  font-size: var(--font-size-base);
}

p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.45;
  font-size: var(--font-size-sm);
}

.agent-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.agent-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

small {
  color: var(--text-tertiary);
}

.empty {
  padding: var(--spacing-xl);
  color: var(--text-tertiary);
}
</style>
