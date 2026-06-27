<template>
  <section class="utility-drawer" :class="{ open }">
    <button
      class="drawer-toggle"
      type="button"
      :aria-expanded="open"
      @click="toggleDrawer"
    >
      <span v-if="!open" class="drawer-toggle-label">{{ t('worldInteraction.utility.toggle') }}</span>
      <el-icon :size="12">
        <ArrowUp v-if="!open" />
        <ArrowDown v-else />
      </el-icon>
    </button>

    <div v-if="open" class="drawer-body">
      <nav
        class="drawer-tab-nav"
        role="tablist"
        aria-orientation="vertical"
        :aria-label="t('worldInteraction.utility.toggle')"
      >
        <button
          type="button"
          class="drawer-tab"
          role="tab"
          :aria-selected="activeTab === 'conversation'"
          :class="{ 'drawer-tab--active': activeTab === 'conversation' }"
          @click="activeTab = 'conversation'"
        >
          {{ t('worldInteraction.utility.conversation') }}
        </button>
        <button
          type="button"
          class="drawer-tab"
          role="tab"
          :aria-selected="activeTab === 'command'"
          :class="{ 'drawer-tab--active': activeTab === 'command' }"
          @click="activeTab = 'command'"
        >
          {{ t('worldInteraction.utility.command') }}
        </button>
      </nav>

      <div class="drawer-content">
        <div v-show="activeTab === 'conversation'" class="drawer-pane" role="tabpanel">
          <div v-if="!conversationEntries.length" class="utility-empty">
            {{ t('worldInteraction.utility.conversationEmpty') }}
          </div>
          <article
            v-for="entry in conversationEntries"
            :key="entry.id"
            class="history-group"
          >
            <div class="history-group-title">{{ entry.title }}</div>
            <div class="history-group-meta">
              {{ t('worldInteraction.utility.messageCount', { count: entry.messageCount }) }}
              <template v-if="entry.preview"> · {{ entry.preview }}</template>
            </div>
          </article>
        </div>

        <div v-show="activeTab === 'command'" class="drawer-pane" role="tabpanel">
          <div v-if="!commandEntries.length" class="utility-empty">
            {{ t('worldInteraction.utility.commandEmpty') }}
          </div>
          <article
            v-for="entry in commandEntries"
            :key="entry.id"
            class="history-group"
          >
            <div class="history-group-title">{{ entry.label }}</div>
            <div v-if="entry.detail && entry.detail !== entry.label" class="history-group-meta">
              {{ entry.detail }}
            </div>
          </article>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { useUtilityHistory } from '@/composables/useUtilityHistory'

const { t } = useI18n()
const open = ref(false)
const activeTab = ref<'conversation' | 'command'>('conversation')
const { conversationEntries, commandEntries, refreshArchivedHistory } = useUtilityHistory()

async function toggleDrawer() {
  open.value = !open.value
}

watch(open, value => {
  if (value) {
    void refreshArchivedHistory()
  }
})
</script>

<style scoped>
.utility-drawer {
  flex-shrink: 0;
  background: var(--decision-query-bg);
}

.drawer-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-xs);
  width: 100%;
  min-height: var(--utility-drawer-bar-height);
  padding: 0 var(--spacing-sm);
  border: 0;
  border-top: 1px solid var(--decision-fold-border);
  background: transparent;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: 1;
  cursor: pointer;
}

.drawer-toggle:hover {
  color: var(--text-secondary);
  background: var(--bg-hover);
}

.drawer-toggle:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

.drawer-toggle-label {
  letter-spacing: 0.02em;
}

.drawer-body {
  display: flex;
  align-items: stretch;
  height: var(--utility-drawer-body-height);
  border-top: 1px solid var(--decision-fold-border);
  min-height: 0;
}

.drawer-tab-nav {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  width: var(--utility-drawer-tab-width);
  border-right: 1px solid var(--decision-fold-border);
  background: var(--decision-fold-interaction-header-bg);
}

.drawer-tab {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  min-height: 0;
  padding: var(--spacing-sm) var(--spacing-xs);
  border: 0;
  border-left: 3px solid transparent;
  background: transparent;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  line-height: 1.3;
  writing-mode: vertical-rl;
  text-orientation: mixed;
  cursor: pointer;
  transition:
    color var(--transition-fast),
    border-color var(--transition-fast),
    background var(--transition-fast);
}

.drawer-tab:hover {
  color: var(--text-secondary);
  background: var(--bg-hover);
}

.drawer-tab--active {
  color: var(--color-primary);
  border-left-color: var(--decision-fold-zone-header-accent);
  background: rgba(64, 158, 255, 0.06);
}

.drawer-tab:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

.drawer-content {
  flex: 1;
  min-width: 0;
  overflow: auto;
  padding: var(--spacing-sm) var(--spacing-md);
}

.drawer-pane {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.utility-empty {
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  padding: var(--spacing-sm) 0;
}

.history-group {
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--border-color-light);
}

.history-group:last-child {
  border-bottom: 0;
}

.history-group-title {
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  line-height: 1.4;
}

.history-group-meta {
  margin-top: 2px;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  line-height: 1.45;
}
</style>
