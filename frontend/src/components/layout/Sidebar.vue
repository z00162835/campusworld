<template>
  <div class="sidebar">
    <div class="sidebar-content">
      <div
        v-for="item in menuItems"
        :key="item.key"
        :class="['sidebar-item', { active: activeKey === item.key }]"
        @click="handleClick(item)"
      >
        <div class="sidebar-icon">
          <component :is="item.icon" />
        </div>
        <span class="sidebar-label">{{ item.label }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useTabsStore } from '@/stores/tabs'
import { useAppTabs } from '@/composables/useAppTabs'
import {
  Document,
  FolderOpened,
  User,
  Search,
  Clock
} from '@element-plus/icons-vue'

interface MenuItem {
  key: string
  label: string
  icon: any
  route: string
}

const tabsStore = useTabsStore()
const { openAppTab } = useAppTabs()

const menuItems: MenuItem[] = [
  {
    key: 'works',
    label: 'Works',
    icon: Document,
    route: '/works'
  },
  {
    key: 'spaces',
    label: 'Spaces',
    icon: FolderOpened,
    route: '/spaces'
  },
  {
    key: 'agents',
    label: 'Agents',
    icon: User,
    route: '/agents'
  },
  {
    key: 'discovery',
    label: 'Discovery',
    icon: Search,
    route: '/discovery'
  },
  {
    key: 'history',
    label: 'History',
    icon: Clock,
    route: '/history'
  }
]

const activeKey = computed(() => tabsStore.activeTab?.route || '')

const handleClick = async (item: MenuItem) => {
  await openAppTab(item.route)
}
</script>

<style scoped>
/* 使用全局样式，这里只保留组件特定的样式 */
</style>
