<template>
  <div class="chat-section">
    <div class="section-header">
      <h3 class="section-title">交互区</h3>
    </div>
    <div class="chat-container">
      <div class="chat-messages" ref="messagesContainer">
        <div
          v-for="message in messages"
          :key="message.id"
          :class="['message', message.role]"
        >
          <div class="message-avatar">
            <el-icon v-if="message.role === 'user'"><User /></el-icon>
            <el-icon v-else><ChatLineRound /></el-icon>
          </div>
          <div class="message-content">
            <div class="message-text">{{ message.content }}</div>
            <div class="message-time">{{ message.time }}</div>
          </div>
        </div>
        <div v-if="messages.length === 0" class="empty-messages">
          <p>开始对话，输入你的问题...</p>
        </div>
      </div>
      <div class="chat-input-wrapper">
        <div class="chat-input-container">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="2"
            placeholder="输入消息..."
            class="chat-input"
            @keydown.ctrl.enter="handleSend"
            @keydown.meta.enter="handleSend"
          />
          <div class="input-actions">
            <el-button
              text
              size="small"
              @click="handleClear"
              :disabled="messages.length === 0"
            >
              <el-icon><Delete /></el-icon>
              清空
            </el-button>
            <el-button
              type="primary"
              :loading="sending"
              :disabled="!inputText.trim()"
              @click="handleSend"
            >
              <el-icon v-if="!sending"><Right /></el-icon>
              {{ sending ? '发送中...' : '发送' }}
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { User, ChatLineRound, Delete, Right } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  time: string
}

const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const sending = ref(false)
const messagesContainer = ref<HTMLElement>()

const formatTime = () => {
  const now = new Date()
  return now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const handleSend = async () => {
  if (!inputText.value.trim() || sending.value) return

  const userMessage: ChatMessage = {
    id: Date.now().toString(),
    role: 'user',
    content: inputText.value.trim(),
    time: formatTime()
  }

  messages.value.push(userMessage)
  const currentInput = inputText.value.trim()
  inputText.value = ''
  sending.value = true

  await scrollToBottom()

  // 模拟 AI 回复
  setTimeout(() => {
    const assistantMessage: ChatMessage = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: `我收到了你的消息："${currentInput}"。这是一个模拟回复，实际功能需要连接后端 API。`,
      time: formatTime()
    }
    messages.value.push(assistantMessage)
    sending.value = false
    scrollToBottom()
  }, 1000)
}

const handleClear = () => {
  messages.value = []
  ElMessage.success('对话已清空')
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}
</script>

<style scoped>
.chat-section {
  margin-bottom: var(--spacing-2xl);
}

.section-header {
  margin-bottom: var(--spacing-lg);
}

.section-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0;
}

.chat-container {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  height: 500px;
  overflow: hidden;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.chat-messages::-webkit-scrollbar {
  width: 6px;
}

.chat-messages::-webkit-scrollbar-track {
  background: transparent;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
}

.message {
  display: flex;
  gap: var(--spacing-md);
  align-items: flex-start;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-hover);
  border-radius: var(--radius-md);
  color: var(--color-primary);
  flex-shrink: 0;
}

.message.user .message-avatar {
  background: var(--color-primary);
  color: #ffffff;
}

.message-content {
  flex: 1;
  min-width: 0;
  max-width: 30%;
}

.message.user .message-content {
  text-align: right;
}

.message-text {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  font-size: var(--font-size-base);
  color: var(--text-primary);
  line-height: 1.6;
  word-break: break-word;
  white-space: pre-wrap;
}

.message.user .message-text {
  background: var(--color-primary);
  color: #ffffff;
  border-color: var(--color-primary);
}

.message-time {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-top: var(--spacing-xs);
}

.empty-messages {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 50%;
  color: var(--text-tertiary);
  font-size: var(--font-size-base);
}

.chat-input-wrapper {
  border-top: 1px solid var(--border-color);
  padding: var(--spacing-md);
  background: var(--bg-secondary);
}

.chat-input-container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.chat-input {
  width: 100%;
}

:deep(.chat-input .el-textarea__inner) {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  font-size: var(--font-size-base);
  resize: none;
}

:deep(.chat-input .el-textarea__inner:focus) {
  border-color: var(--color-primary);
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
}
</style>

