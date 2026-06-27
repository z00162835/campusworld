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
            <app-icon class="app-nav-icon" :name="item.iconKey" :size="16" />
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
import { ArrowDown } from '@element-plus/icons-vue'
import AppIcon from '@/components/common/AppIcon.vue'
import { useAppTabs } from '@/composables/useAppTabs'
import { APP_TAB_DEFINITIONS } from '@/stores/appTabs'
import { useTabsStore } from '@/stores/tabs'

const { t } = useI18n()
const tabsStore = useTabsStore()
const { openAppTab } = useAppTabs()

const menuItems = APP_TAB_DEFINITIONS.filter(tab => tab.route !== '/profile').map(tab => ({
  key: tab.id,
  labelKey: tab.titleKey || tab.route,
  route: tab.route,
  iconKey: tab.iconKey,
}))

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
  color: var(--text-secondary);
}
</style>
