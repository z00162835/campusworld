<template>
  <div class="tab-bar" v-if="tabs.length > 0">
    <div class="tab-list">
      <div
        v-for="tab in tabs"
        :key="tab.id"
        :class="['tab-item', { active: tab.id === activeTabId }]"
        @click="handleTabClick(tab.id)"
      >
        <span class="tab-title">{{ tab.titleKey ? t(tab.titleKey) : tab.title }}</span>
        <el-icon
          v-if="tab.closable"
          class="tab-close"
          @click.stop="handleTabClose(tab.id)"
        >
          <Close />
        </el-icon>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTabsStore } from '@/stores/tabs'
import { useAppTabs } from '@/composables/useAppTabs'
import { Close } from '@element-plus/icons-vue'

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
/* 使用全局样式，这里只保留组件特定的样式 */
</style>
