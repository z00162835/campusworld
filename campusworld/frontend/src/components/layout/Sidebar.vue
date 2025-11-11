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
  component: string
}

const tabsStore = useTabsStore()

const menuItems: MenuItem[] = [
  {
    key: 'works',
    label: 'Works',
    icon: Document,
    route: '/works',
    component: 'Home'
  },
  {
    key: 'spaces',
    label: 'Spaces',
    icon: FolderOpened,
    route: '/spaces',
    component: 'Spaces'
  },
  {
    key: 'agents',
    label: 'Agents',
    icon: User,
    route: '/agents',
    component: 'Agents'
  },
  {
    key: 'discovery',
    label: 'Discovery',
    icon: Search,
    route: '/discovery',
    component: 'Discovery'
  },
  {
    key: 'history',
    label: 'History',
    icon: Clock,
    route: '/history',
    component: 'History'
  }
]

const activeKey = computed(() => {
  return tabsStore.activeTab?.route || ''
})

const handleClick = (item: MenuItem) => {
  // 使用固定的ID，基于route，这样同一个route只会有一个tab
  const tabId = `tab-${item.key}`
  tabsStore.addTab({
    id: tabId,
    title: item.label,
    route: item.route,
    component: item.component,
    closable: true
  })
}
</script>

<style scoped>
/* 使用全局样式，这里只保留组件特定的样式 */
</style>

