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
        class="navbar-button"
        @click="handleLogin"
      >
        登录
      </el-button>
      <el-button
        v-if="!isAuthenticated"
        text
        class="navbar-button"
        @click="handleRegister"
      >
        注册
      </el-button>
      <el-dropdown
        v-if="isAuthenticated"
        trigger="click"
        @command="handleCommand"
      >
        <el-button text class="navbar-button">
          <el-icon><Setting /></el-icon>
          <span style="margin-left: 4px">设置</span>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">个人资料</el-dropdown-item>
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
import { ElMessage } from 'element-plus'
import { Setting } from '@element-plus/icons-vue'

const router = useRouter()

const isAuthenticated = computed(() => {
  return !!localStorage.getItem('access_token')
})

const handleLogin = () => {
  router.push('/login')
}

const handleRegister = () => {
  router.push('/register')
}

const handleCommand = (command: string) => {
  if (command === 'profile') {
    router.push('/profile')
  } else if (command === 'logout') {
    localStorage.removeItem('access_token')
    ElMessage.success('已退出登录')
    router.push('/')
  }
}
</script>

<style scoped>
/* 确保 NavBar 按钮样式优先级最高，覆盖所有 Element Plus 默认样式 */
.navbar-button:deep(.el-button) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  outline: none !important;
  padding: 0 !important;
}

.navbar-button:deep(.el-button:hover) {
  background: var(--bg-hover) !important;
  border: none !important;
  box-shadow: none !important;
  outline: none !important;
  color: var(--text-secondary) !important;
}

.navbar-button:deep(.el-button:focus),
.navbar-button:deep(.el-button:active) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  outline: none !important;
}

/* 覆盖按钮内部所有可能的 wrapper 元素 */
.navbar-button:deep(.el-button__inner),
.navbar-button:deep(.el-button__wrapper),
.navbar-button:deep(.el-button > span),
.navbar-button:deep(.el-button > *) {
  background: transparent !important;
  color: inherit !important;
}

.navbar-button:hover:deep(.el-button__inner),
.navbar-button:hover:deep(.el-button__wrapper),
.navbar-button:hover:deep(.el-button > span),
.navbar-button:hover:deep(.el-button > *) {
  background: transparent !important;
  color: var(--text-secondary) !important;
}

/* 移除所有伪元素 */
.navbar-button:deep(.el-button::before),
.navbar-button:deep(.el-button::after),
.navbar-button:deep(.el-button__inner::before),
.navbar-button:deep(.el-button__inner::after) {
  display: none !important;
  background: transparent !important;
}
</style>
