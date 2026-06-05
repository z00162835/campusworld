<template>
  <div ref="scrollRoot" class="conversation-thread-viewport">
    <div class="conversation-thread">
      <p v-if="worldSession.conversationAtCap" class="cap-hint">
        {{ t('worldInteraction.decision.olderHistoryHint') }}
      </p>
      <query-result-card
        v-for="message in worldSession.conversationMessages"
        :key="message.id"
        :message="message"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import QueryResultCard from './QueryResultCard.vue'
import { useWorldSessionStore } from '@/stores/worldSession'
import { scrollElementToBottom } from '@/utils/scrollToBottom'

const { t } = useI18n()
const worldSession = useWorldSessionStore()
const scrollRoot = ref<HTMLElement>()

async function scrollToBottom() {
  await scrollElementToBottom(scrollRoot.value)
}

watch(
  () =>
    worldSession.conversationMessages
      .map(msg => `${msg.id}:${msg.answer.length}:${msg.streaming}:${msg.streamStatusKey ?? ''}`)
      .join('|'),
  () => {
    void scrollToBottom()
  },
  { flush: 'post' },
)

defineExpose({ scrollToBottom })
</script>

<style scoped>
.conversation-thread-viewport {
  flex: 1 1 0;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.conversation-thread {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  min-height: min-content;
}

.cap-hint {
  margin: 0;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
</style>
