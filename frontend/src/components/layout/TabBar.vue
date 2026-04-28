<template>
  <div class="tab-bar" v-if="tabs.length > 0">
    <div class="tab-list">
      <div
        v-for="tab in tabs"
        :key="tab.id"
        :class="['tab-item', { active: tab.id === activeTabId }]"
        @click="handleTabClick(tab.id)"
      >
        <span class="tab-title">{{ tab.title }}</span>
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
import { useTabsStore } from '@/stores/tabs'
import { Close } from '@element-plus/icons-vue'

const tabsStore = useTabsStore()

const tabs = computed(() => tabsStore.tabs)
const activeTabId = computed(() => tabsStore.activeTabId)

const handleTabClick = (tabId: string) => {
  tabsStore.setActiveTab(tabId)
}

const handleTabClose = (tabId: string) => {
  tabsStore.removeTab(tabId)
}
</script>

<style scoped>
/* 使用全局样式，这里只保留组件特定的样式 */
</style>

