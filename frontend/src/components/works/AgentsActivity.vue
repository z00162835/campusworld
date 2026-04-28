<template>
  <div class="agents-section">
    <div class="section-header">
      <h3 class="section-title">Agents 活动</h3>
      <el-button text size="small" @click="handleRefresh">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>
    <div class="agents-list">
      <div
        v-for="agent in agents"
        :key="agent.id"
        class="agent-item"
      >
        <div class="agent-avatar">
          <el-icon :size="20"><User /></el-icon>
        </div>
        <div class="agent-content">
          <div class="agent-header">
            <span class="agent-name">{{ agent.name }}</span>
            <span class="agent-status" :class="agent.status">
              {{ getStatusLabel(agent.status) }}
            </span>
          </div>
          <div class="agent-activity">{{ agent.activity }}</div>
          <div class="agent-time">{{ agent.time }}</div>
        </div>
      </div>
      <div v-if="agents.length === 0" class="empty-agents">
        <p>暂无 Agents 活动</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { User, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

interface Agent {
  id: string
  name: string
  status: 'active' | 'idle' | 'busy'
  activity: string
  time: string
}

const agents = ref<Agent[]>([
  {
    id: '1',
    name: 'Code Agent',
    status: 'active',
    activity: '正在分析代码库结构，准备生成文档',
    time: '2分钟前'
  },
  {
    id: '2',
    name: 'Data Agent',
    status: 'busy',
    activity: '处理数据清洗任务，进度 75%',
    time: '5分钟前'
  },
  {
    id: '3',
    name: 'Research Agent',
    status: 'idle',
    activity: '等待新的研究任务',
    time: '10分钟前'
  },
  {
    id: '4',
    name: 'Design Agent',
    status: 'active',
    activity: '正在生成 UI 设计方案',
    time: '1分钟前'
  }
])

const handleRefresh = () => {
  ElMessage.success('已刷新')
}

const getStatusLabel = (status: string) => {
  const labels = {
    active: '运行中',
    idle: '空闲',
    busy: '忙碌'
  }
  return labels[status as keyof typeof labels] || status
}
</script>

<style scoped>
.agents-section {
  margin-bottom: var(--spacing-2xl);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-lg);
}

.section-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
}

.agents-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.agent-item {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-md);
  transition: all var(--transition-fast);
}

.agent-item:hover {
  border-color: var(--border-color-dark);
  background: var(--bg-secondary);
}

.agent-avatar {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  color: var(--color-primary);
  flex-shrink: 0;
}

.agent-content {
  flex: 1;
  min-width: 0;
}

.agent-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-xs);
}

.agent-name {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}

.agent-status {
  font-size: var(--font-size-xs);
  padding: 2px var(--spacing-xs);
  border-radius: var(--radius-sm);
}

.agent-status.active {
  background: rgba(64, 158, 255, 0.2);
  color: var(--color-primary);
}

.agent-status.idle {
  background: rgba(144, 147, 153, 0.2);
  color: var(--color-info);
}

.agent-status.busy {
  background: rgba(230, 162, 60, 0.2);
  color: var(--color-warning);
}

.agent-activity {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-bottom: var(--spacing-xs);
  word-break: break-word;
}

.agent-time {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}

.empty-agents {
  text-align: center;
  padding: var(--spacing-2xl);
  color: var(--text-tertiary);
  font-size: var(--font-size-base);
}
</style>

