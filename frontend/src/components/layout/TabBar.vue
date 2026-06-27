<template>
  <div class="tab-bar" v-if="tabs.length > 0">
    <div class="tab-list">
      <div
        v-for="tab in tabs"
        :key="tab.id"
        :class="['tab-item', { active: tab.id === activeTabId }]"
        @click="handleTabClick(tab.id)"
      >
        <span class="tab-leading">
          <app-icon
            class="tab-icon"
            :name="tab.iconKey"
            :size="16"
          />
          <span class="tab-title">{{ tab.titleKey ? t(tab.titleKey) : tab.title }}</span>
        </span>
        <button
          v-if="tab.closable"
          type="button"
          class="tab-close"
          @click.stop="handleTabClose(tab.id)"
        >
          <app-icon name="close" :size="14" />
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/common/AppIcon.vue'
import { useTabsStore } from '@/stores/tabs'
import { useAppTabs } from '@/composables/useAppTabs'

const tabsStore = useTabsStore()
const { t } = useI18n()
const { activateAppTab, closeAppTab } = useAppTabs()

const tabs = computed(() => tabsStore.tabs)
const activeTabId = computed(() => tabsStore.activeTabId)

const handleTabClick = async (tabId: string) => {
  await activateAppTab(tabId)
}

const handleTabClose = async (tabId: string) => {
  await closeAppTab(tabId)
}
</script>

<style scoped>
/* Component-specific overrides only; shared styles live in tabbar.css */
</style>
