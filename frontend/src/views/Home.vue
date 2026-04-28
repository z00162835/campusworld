<template>
  <div class="works-home">
    <div class="works-container">
      <!-- Dashboard 区域 -->
      <dashboard />
      
      <!-- 待办任务区域 -->
      <todo-list />
      
      <!-- Agents 信息区 -->
      <agents-activity />
      
      <!-- 交互区 -->
      <chat-input />
    </div>
  </div>
</template>

<script setup lang="ts">
import Dashboard from '@/components/works/Dashboard.vue'
import TodoList from '@/components/works/TodoList.vue'
import AgentsActivity from '@/components/works/AgentsActivity.vue'
import ChatInput from '@/components/works/ChatInput.vue'
</script>

<style scoped>
.works-home {
  width: 100%;
  height: 100%;
  overflow-y: auto;
}

.works-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: var(--spacing-xl);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2xl);
}

/* 响应式设计 */
@media (max-width: 768px) {
  .works-container {
    padding: var(--spacing-lg);
    gap: var(--spacing-xl);
  }
}
</style>
