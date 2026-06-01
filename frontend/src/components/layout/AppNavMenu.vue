<template>
  <el-dropdown
    trigger="click"
    placement="bottom-start"
    effect="dark"
    popper-class="cw-dropdown-popper"
    @command="handleCommand"
  >
    <button class="app-nav-trigger" type="button">
      <span class="app-nav-brand">CampusWorld</span>
      <el-icon class="app-nav-chevron"><ArrowDown /></el-icon>
    </button>
    <template #dropdown>
      <el-dropdown-menu class="app-nav-menu">
        <el-dropdown-item
          v-for="item in menuItems"
          :key="item.key"
          :command="item.route"
          :class="{ 'is-active': activeRoute === item.route }"
        >
          <span class="app-nav-item">
            <el-icon class="app-nav-icon"><component :is="item.icon" /></el-icon>
            <span>{{ t(item.labelKey) }}</span>
          </span>
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowDown, Clock, Document, FolderOpened, Search, User } from '@element-plus/icons-vue'
import { useAppTabs } from '@/composables/useAppTabs'
import { useTabsStore } from '@/stores/tabs'

interface MenuItem {
  key: string
  labelKey: string
  icon: typeof Document
  route: string
}

const { t } = useI18n()
const tabsStore = useTabsStore()
const { openAppTab } = useAppTabs()

const menuItems: MenuItem[] = [
  { key: 'works', labelKey: 'nav.works', icon: Document, route: '/works' },
  { key: 'spaces', labelKey: 'nav.spaces', icon: FolderOpened, route: '/spaces' },
  { key: 'agents', labelKey: 'nav.agents', icon: User, route: '/agents' },
  { key: 'discovery', labelKey: 'nav.discovery', icon: Search, route: '/discovery' },
  { key: 'history', labelKey: 'nav.history', icon: Clock, route: '/history' },
]

const activeRoute = computed(() => tabsStore.activeTab?.route || '')

const handleCommand = async (route: string) => {
  await openAppTab(route)
}
</script>

<style scoped>
.app-nav-trigger {
  border: 0;
  background: transparent;
  color: var(--text-primary);
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  cursor: pointer;
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-md);
}

.app-nav-trigger:hover {
  background: var(--bg-hover);
}

.app-nav-brand {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  letter-spacing: 0.5px;
}

.app-nav-chevron {
  color: var(--text-tertiary);
  font-size: 14px;
}

.app-nav-item {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-sm);
  min-width: 140px;
}

.app-nav-icon {
  font-size: 16px;
}
</style>
