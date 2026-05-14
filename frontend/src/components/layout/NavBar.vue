<template>
  <div class="navbar">
    <div class="navbar-left">
      <div class="logo">
        <span class="logo-text">CampusWorld</span>
      </div>
    </div>
    <div class="navbar-right">
      <el-button
        v-if="!isAuthenticated"
        text
        class="cw-text-button"
        @click="handleLogin"
      >
        登录
      </el-button>
      <el-button
        v-if="!isAuthenticated"
        text
        class="cw-text-button"
        @click="handleRegister"
      >
        注册
      </el-button>
      <el-dropdown
        v-if="isAuthenticated"
        trigger="click"
        @command="handleCommand"
      >
        <el-button text class="cw-text-button">
          <el-icon><Setting /></el-icon>
          <span style="margin-left: 4px">设置</span>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">账号设置</el-dropdown-item>
            <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Setting } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useLogout } from '@/composables/useLogout'
import { useAppTabs } from '@/composables/useAppTabs'

const router = useRouter()
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
