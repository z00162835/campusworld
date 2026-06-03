<template>
  <article class="query-result-card" :class="{ expanded: isExpanded, streaming: message.streaming }">
    <header>
      <span class="role">{{ roleLabel }}</span>
      <span v-if="message.cancelled" class="cancelled">{{ t('worldInteraction.decision.cancelled') }}</span>
    </header>

    <p v-if="message.role === 'user'" class="user-text">{{ message.query || message.answer }}</p>

    <template v-else>
      <div class="card-body">
        <p
          v-if="showStreamStatus"
          class="stream-status"
          :class="{ 'stream-status--active': message.streaming }"
          role="status"
          aria-live="polite"
        >
          <span class="stream-status-text">{{ streamStatusLabel }}</span>
          <stream-typing-dots v-if="message.streaming" />
        </p>
        <div v-if="showAnswerBody" class="answer-output">
          <markdown-content v-if="renderAnswerAsMarkdown" :source="displayText" />
          <p v-else class="command-output">{{ displayText }}</p>
          <span v-if="showAnswerCaret" class="stream-caret" aria-hidden="true" />
        </div>

        <ul v-if="message.results?.length" class="results-list">
          <li v-for="item in message.results" :key="item.entity_id">
            <strong>{{ item.title }}</strong>
            <span>{{ item.summary }}</span>
          </li>
        </ul>
      </div>

      <button
        v-if="canExpand"
        type="button"
        class="expand-toggle"
        @click="worldSession.toggleMessageExpanded(message.id)"
      >
        {{ isExpanded ? t('worldInteraction.decision.collapse') : t('worldInteraction.decision.expand') }}
      </button>
    </template>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import MarkdownContent from './MarkdownContent.vue'
import StreamTypingDots from './StreamTypingDots.vue'
import { useWorldSessionStore } from '@/stores/worldSession'
import type { ConversationMessage } from '@/types/world'

const props = defineProps<{
  message: ConversationMessage
}>()

const { t } = useI18n()
const worldSession = useWorldSessionStore()

const roleLabel = computed(() => {
  if (props.message.role === 'user') {
    return t('worldInteraction.decision.messageRole.you')
  }
  if (props.message.mode === 'aico') {
    return t('worldInteraction.decision.messageRole.aico')
  }
  return t('worldInteraction.decision.messageRole.assistant')
})

const displayText = computed(
  () => props.message.commandResult?.message || props.message.answer || '',
)

const streamStatusLabel = computed(() => {
  const key = props.message.streamStatusKey
  if (key) return t(`worldInteraction.decision.streamStatus.${key}`)
  if (props.message.streaming) return t('worldInteraction.decision.streamStatus.generating')
  return ''
})

const showStreamStatus = computed(
  () => props.message.streaming === true || Boolean(props.message.streamStatusKey),
)

const showAnswerBody = computed(() => Boolean(displayText.value.trim()))

const showAnswerCaret = computed(
  () => props.message.streaming === true && Boolean(displayText.value.trim()),
)

const renderAnswerAsMarkdown = computed(
  () => props.message.mode === 'aico' && props.message.role === 'assistant',
)

const isExpanded = computed(() => props.message.expanded === true)

const canExpand = computed(() => {
  if (props.message.role === 'user' || props.message.streaming) return false
  const text = displayText.value
  const hasResults = (props.message.results?.length || 0) > 0
  return Boolean(text.trim()) || hasResults
})
</script>

<style scoped>
.query-result-card {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: #1b1f26;
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  flex-shrink: 0;
}

.card-body {
  min-height: 0;
}

.query-result-card:not(.expanded):not(.streaming) .card-body {
  max-height: 120px;
  overflow: hidden;
}

.query-result-card.expanded .card-body,
.query-result-card.streaming .card-body {
  max-height: none;
  overflow: visible;
}

.query-result-card.streaming .card-body {
  min-height: 2.5rem;
}

header {
  display: flex;
  gap: var(--spacing-sm);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  text-transform: uppercase;
  flex-shrink: 0;
}

.stream-status {
  margin: 0 0 var(--spacing-xs);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0;
}

.stream-status--active .stream-status-text {
  animation: stream-status-pulse 2s ease-in-out infinite;
}

@keyframes stream-status-pulse {
  0%,
  100% {
    opacity: 0.72;
  }

  50% {
    opacity: 1;
  }
}

.user-text,
.command-output {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.answer-output {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0;
}

.command-output {
  color: var(--text-primary);
  flex: 1 1 100%;
}

.results-list {
  margin: var(--spacing-xs) 0 0;
  padding-left: var(--spacing-lg);
  color: var(--text-secondary);
}

.results-list li {
  margin-bottom: var(--spacing-xs);
}

.results-list strong {
  display: block;
  color: var(--text-primary);
}

.expand-toggle {
  align-self: flex-start;
  flex-shrink: 0;
  border: 0;
  background: transparent;
  color: var(--color-primary);
  cursor: pointer;
  font-size: var(--font-size-xs);
  padding: var(--spacing-xs) 0 0;
}

.expand-toggle:hover {
  text-decoration: underline;
}

.stream-caret {
  display: inline-block;
  width: 2px;
  height: 1.05em;
  margin-left: 2px;
  border-radius: 1px;
  background: var(--color-primary);
  vertical-align: text-bottom;
  animation: stream-caret-pulse 0.9s ease-in-out infinite;
}

@keyframes stream-caret-pulse {
  0%,
  100% {
    opacity: 0.35;
  }

  50% {
    opacity: 1;
  }
}

.cancelled {
  color: var(--color-warning);
}
</style>
