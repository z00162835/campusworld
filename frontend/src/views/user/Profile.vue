<template>
  <div class="account-settings">
    <div class="settings-container">
      <header class="settings-header">
        <div>
          <h2 class="settings-title">账号设置</h2>
        </div>
        <el-button text class="settings-close" @click="handleClose">
          <el-icon><Close /></el-icon>
        </el-button>
      </header>

      <section class="settings-section">
        <div class="section-heading">
          <h3>个人资料</h3>
          <span>当前账号的展示信息</span>
        </div>
        <div class="profile-fields">
          <div class="field-row">
            <span class="field-label">用户名</span>
            <span class="field-value">{{ authStore.user?.username || '未设置' }}</span>
          </div>
          <div class="field-row">
            <span class="field-label">邮箱</span>
            <span class="field-value">{{ authStore.user?.email || '未设置' }}</span>
          </div>
        </div>
      </section>

      <section class="settings-section">
        <div class="section-heading">
          <h3>账号安全</h3>
        </div>
        <div class="security-actions security-actions--simple">
          <el-button type="danger" @click="handleLogout">退出登录</el-button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Close } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useLogout } from '@/composables/useLogout'
import { useAppTabs } from '@/composables/useAppTabs'

const authStore = useAuthStore()
const { logout } = useLogout()
const { openAppTab } = useAppTabs()

onMounted(async () => {
  if (!authStore.user && authStore.token) {
    await authStore.fetchUser()
  }
})

const handleClose = () => {
  openAppTab('/works')
}

const handleLogout = async () => {
  await logout()
  ElMessage.success('已退出登录')
}
</script>

<style scoped>
.account-settings {
  width: 100%;
  height: 100%;
  overflow-y: auto;
}

.settings-container {
  max-width: 960px;
  margin: 0 auto;
  padding: var(--spacing-xl);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
}

.settings-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-lg);
}

.settings-title {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
}

.settings-close {
  color: var(--text-tertiary);
}

.settings-section {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-xl);
}

.section-heading {
  margin-bottom: var(--spacing-lg);
}

.section-heading h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
}

.section-heading span {
  display: block;
  margin-top: var(--spacing-xs);
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
}

.profile-fields {
  display: grid;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.field-row {
  display: grid;
  grid-template-columns: minmax(120px, 180px) 1fr;
  min-height: 48px;
  border-bottom: 1px solid var(--border-color);
}

.field-row:last-child {
  border-bottom: none;
}

.field-label,
.field-value {
  display: flex;
  align-items: center;
  padding: 0 var(--spacing-lg);
  min-width: 0;
}

.field-label {
  color: var(--text-tertiary);
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
}

.field-value {
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

.security-actions {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: var(--spacing-lg);
}

@media (max-width: 768px) {
  .settings-container {
    padding: var(--spacing-lg);
  }

  .field-row {
    grid-template-columns: 1fr;
  }

  .field-label {
    min-height: 40px;
    border-right: none;
    border-bottom: 1px solid var(--border-color);
  }

  .field-value {
    min-height: 44px;
  }

  .security-actions--simple :deep(.el-button) {
    width: 100%;
  }
}
</style>
