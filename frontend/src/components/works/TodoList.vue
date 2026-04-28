<template>
  <div class="todo-section">
    <div class="section-header">
      <h3 class="section-title">待办任务</h3>
      <el-button text size="small" @click="handleAddTask">
        <el-icon><Plus /></el-icon>
        添加任务
      </el-button>
    </div>
    <div class="todo-list">
      <div
        v-for="task in tasks"
        :key="task.id"
        :class="['todo-item', { completed: task.completed }]"
        @click="toggleTask(task.id)"
      >
        <div class="todo-checkbox">
          <el-icon v-if="task.completed" class="checked-icon">
            <Check />
          </el-icon>
          <div v-else class="unchecked-box"></div>
        </div>
        <div class="todo-content">
          <div class="todo-title">{{ task.title }}</div>
          <div class="todo-meta">
            <span class="todo-priority" :class="task.priority">
              {{ getPriorityLabel(task.priority) }}
            </span>
            <span class="todo-time">{{ task.time }}</span>
          </div>
        </div>
        <el-button
          text
          size="small"
          class="todo-delete"
          @click.stop="deleteTask(task.id)"
        >
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
      <div v-if="tasks.length === 0" class="empty-todo">
        <p>暂无待办任务</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Plus, Check, Delete } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

interface TodoTask {
  id: string
  title: string
  completed: boolean
  priority: 'high' | 'medium' | 'low'
  time: string
}

const tasks = ref<TodoTask[]>([
  {
    id: '1',
    title: '完成项目文档编写',
    completed: false,
    priority: 'high',
    time: '今天 14:00'
  },
  {
    id: '2',
    title: '代码审查和优化',
    completed: false,
    priority: 'medium',
    time: '今天 16:00'
  },
  {
    id: '3',
    title: '准备下周的会议材料',
    completed: true,
    priority: 'low',
    time: '明天 10:00'
  }
])

const toggleTask = (id: string) => {
  const task = tasks.value.find(t => t.id === id)
  if (task) {
    task.completed = !task.completed
  }
}

const deleteTask = (id: string) => {
  const index = tasks.value.findIndex(t => t.id === id)
  if (index > -1) {
    tasks.value.splice(index, 1)
    ElMessage.success('任务已删除')
  }
}

const handleAddTask = () => {
  ElMessage.info('添加任务功能开发中')
}

const getPriorityLabel = (priority: string) => {
  const labels = {
    high: '高优先级',
    medium: '中优先级',
    low: '低优先级'
  }
  return labels[priority as keyof typeof labels] || priority
}
</script>

<style scoped>
.todo-section {
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

.todo-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.todo-item {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.todo-item:hover {
  border-color: var(--border-color-dark);
  background: var(--bg-secondary);
}

.todo-item.completed {
  opacity: 0.6;
}

.todo-item.completed .todo-title {
  text-decoration: line-through;
  color: var(--text-tertiary);
}

.todo-checkbox {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.checked-icon {
  color: var(--color-success);
  font-size: 20px;
}

.unchecked-box {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: transparent;
}

.todo-content {
  flex: 1;
  min-width: 0;
}

.todo-title {
  font-size: var(--font-size-base);
  color: var(--text-primary);
  margin-bottom: var(--spacing-xs);
  word-break: break-word;
}

.todo-meta {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  font-size: var(--font-size-sm);
}

.todo-priority {
  padding: 2px var(--spacing-xs);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
}

.todo-priority.high {
  background: rgba(245, 108, 108, 0.2);
  color: var(--color-danger);
}

.todo-priority.medium {
  background: rgba(230, 162, 60, 0.2);
  color: var(--color-warning);
}

.todo-priority.low {
  background: rgba(103, 194, 58, 0.2);
  color: var(--color-success);
}

.todo-time {
  color: var(--text-tertiary);
}

.todo-delete {
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.todo-item:hover .todo-delete {
  opacity: 1;
}

.empty-todo {
  text-align: center;
  padding: var(--spacing-2xl);
  color: var(--text-tertiary);
  font-size: var(--font-size-base);
}
</style>

