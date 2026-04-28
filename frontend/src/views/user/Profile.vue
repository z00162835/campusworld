<template>
  <div class="profile">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>个人资料</span>
          <el-button text @click="handleClose">
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
      </template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="用户名">
          {{ authStore.user?.username || '未设置' }}
        </el-descriptions-item>
        <el-descriptions-item label="邮箱">
          {{ authStore.user?.email || '未设置' }}
        </el-descriptions-item>
      </el-descriptions>
      <el-button type="danger" @click="handleLogout" style="margin-top: var(--spacing-xl)">
        退出登录
      </el-button>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Close } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

onMounted(async () => {
  // Only fetch user if we have a token but no cached user
  if (!authStore.user && authStore.token) {
    await authStore.fetchUser()
  }
})

const handleClose = () => {
  router.push('/works')
}

const handleLogout = async () => {
  try {
    await authStore.logout()
    ElMessage.success('已退出登录')
  } catch {
    // Still navigate even if logout fails
  } finally {
    await nextTick()
    router.push('/login')
  }
}
</script>

<style scoped>
.profile {
  padding: var(--spacing-xl);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

.card-header .el-button {
  margin-left: auto;
  padding: var(--spacing-sm);
}
</style>
