<template>
  <div class="profile">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>个人资料</span>
        </div>
      </template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="用户名">
          {{ userInfo.username || '未设置' }}
        </el-descriptions-item>
        <el-descriptions-item label="邮箱">
          {{ userInfo.email || '未设置' }}
        </el-descriptions-item>
      </el-descriptions>
      <el-button type="danger" @click="handleLogout" style="margin-top: var(--spacing-xl)">
        退出登录
      </el-button>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const router = useRouter()
const userInfo = ref({
  username: '',
  email: ''
})

onMounted(async () => {
  try {
    const token = localStorage.getItem('access_token')
    if (!token) {
      // 屏蔽登录要求，显示默认信息
      userInfo.value = {
        username: '访客',
        email: 'guest@example.com'
      }
      return
    }
    
    const response = await axios.get('/api/v1/accounts/me', {
      headers: {
        Authorization: `Bearer ${token}`
      }
    })
    
    userInfo.value = response.data
  } catch (error) {
    // 屏蔽登录要求，显示默认信息
    userInfo.value = {
      username: '访客',
      email: 'guest@example.com'
    }
  }
})

const handleLogout = () => {
  localStorage.removeItem('access_token')
  ElMessage.success('已退出登录')
  router.push('/')
}
</script>

<style scoped>
.profile {
  padding: var(--spacing-xl);
}

.card-header {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
}
</style>

