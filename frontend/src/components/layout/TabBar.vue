<template>
  <div class="tab-bar" v-if="tabs.length > 0">
    <div
      class="tab-list"
      role="tablist"
      :aria-label="t('nav.tabsLabel')"
    >
      <div
        v-for="(tab, index) in tabs"
        :key="tab.id"
        class="tab-entry"
        :class="{ active: tab.id === activeTabId }"
      >
        <button
          :id="`app-tab-${tab.id}`"
          type="button"
          class="tab-item"
          role="tab"
          :aria-selected="tab.id === activeTabId"
          :tabindex="tab.id === activeTabId ? 0 : -1"
          :aria-keyshortcuts="tab.closable ? 'Delete' : undefined"
          :title="tab.closable ? tabCloseHint(tab) : undefined"
          @click="handleTabClick(tab.id)"
          @keydown="handleTabKeydown($event, index)"
        >
          <span class="tab-leading">
            <app-icon
              class="tab-icon"
              :name="tab.iconKey"
              :size="16"
            />
            <span class="tab-title">{{ tab.titleKey ? t(tab.titleKey) : tab.title }}</span>
          </span>
        </button>
        <button
          v-if="tab.closable"
          type="button"
          class="tab-close"
          tabindex="-1"
          aria-hidden="true"
          @click.stop="handleTabClose(tab.id, index)"
        >
          <app-icon name="close" :size="14" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/common/AppIcon.vue'
import { useTabsStore } from '@/stores/tabs'
import { useAppTabs } from '@/composables/useAppTabs'

const tabsStore = useTabsStore()
const { t } = useI18n()
const { activateAppTab, closeAppTab } = useAppTabs()

const tabs = computed(() => tabsStore.tabs)
const activeTabId = computed(() => tabsStore.activeTabId)

function tabCloseHint(tab: (typeof tabs.value)[number]) {
  const title = tab.titleKey ? t(tab.titleKey) : tab.title
  return t('nav.closeTabShortcut', { title })
}

const handleTabClick = async (tabId: string) => {
  await activateAppTab(tabId)
}

const handleTabClose = async (tabId: string, closedIndex: number) => {
  await closeAppTab(tabId)
  await nextTick()
  const remaining = tabs.value
  if (remaining.length === 0) return
  const focusIndex = Math.min(closedIndex, remaining.length - 1)
  document.getElementById(`app-tab-${remaining[focusIndex]?.id}`)?.focus()
}

async function activateTabAt(index: number) {
  const tab = tabs.value[index]
  if (!tab) return
  await activateAppTab(tab.id)
  await nextTick()
  document.getElementById(`app-tab-${tab.id}`)?.focus()
}

function handleTabKeydown(event: KeyboardEvent, index: number) {
  const tab = tabs.value[index]
  if (!tab) return

  if (event.key === 'ArrowRight') {
    event.preventDefault()
    void activateTabAt((index + 1) % tabs.value.length)
    return
  }
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    void activateTabAt((index - 1 + tabs.value.length) % tabs.value.length)
    return
  }
  if (event.key === 'Home') {
    event.preventDefault()
    void activateTabAt(0)
    return
  }
  if (event.key === 'End') {
    event.preventDefault()
    void activateTabAt(tabs.value.length - 1)
    return
  }
  if ((event.key === 'Delete' || event.key === 'Backspace') && tab.closable) {
    event.preventDefault()
    void handleTabClose(tab.id, index)
  }
}
</script>

<style scoped>
/* Component-specific overrides only; shared styles live in tabbar.css */
</style>
