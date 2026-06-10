<template>
  <div class="navbar">
    <div class="navbar-left">
      <app-nav-menu />
    </div>
    <div class="navbar-right">
      <el-button
        v-if="!isAuthenticated"
        text
        class="cw-text-button"
        @click="handleLogin"
      >
        {{ t('auth.login') }}
      </el-button>
      <el-button
        v-if="!isAuthenticated"
        text
        class="cw-text-button"
        @click="handleRegister"
      >
        {{ t('auth.register') }}
      </el-button>
      <el-dropdown
        v-if="isAuthenticated"
        trigger="click"
        effect="dark"
        popper-class="cw-dropdown-popper"
        @command="handleCommand"
      >
        <el-button text class="cw-text-button">
          <el-icon><Setting /></el-icon>
          <span style="margin-left: 4px">{{ t('shell.settings') }}</span>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu class="cw-settings-menu">
            <el-dropdown-item command="profile">{{ t('shell.accountSettings') }}</el-dropdown-item>
            <el-dropdown-item command="logout" divided>{{ t('shell.logout') }}</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Setting } from '@element-plus/icons-vue'
import AppNavMenu from './AppNavMenu.vue'
import { useAuthStore } from '@/stores/auth'
import { useLogout } from '@/composables/useLogout'
import { useAppTabs } from '@/composables/useAppTabs'

const router = useRouter()
const { t } = useI18n()
const authStore = useAuthStore()
const { logout } = useLogout()
const { openAppTab } = useAppTabs()

const isAuthenticated = computed(() => {
  return authStore.isAuthenticated
})

const handleLogin = () => {
  router.push('/login')
}

const handleRegister = () => {
  router.push('/register')
}

const handleCommand = async (command: string) => {
  if (command === 'profile') {
    await openAppTab('/profile')
  } else if (command === 'logout') {
    await logout()
  }
}
</script>
