<template>
  <div ref="threadRoot" class="conversation-thread">
    <p v-if="worldSession.conversationAtCap" class="cap-hint">
      {{ t('worldInteraction.decision.olderHistoryHint') }}
    </p>
    <query-result-card
      v-for="message in worldSession.conversationMessages"
      :key="message.id"
      :message="message"
    />
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import QueryResultCard from './QueryResultCard.vue'
import { useWorldSessionStore } from '@/stores/worldSession'

const { t } = useI18n()
const worldSession = useWorldSessionStore()
const threadRoot = ref<HTMLElement>()

async function scrollToBottom() {
  await nextTick()
  const el = threadRoot.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

watch(
  () =>
    worldSession.conversationMessages
      .map(msg => `${msg.id}:${msg.answer.length}:${msg.streaming}:${msg.streamStatusKey ?? ''}`)
      .join('|'),
  () => {
    void scrollToBottom()
  },
)

defineExpose({ scrollToBottom })
</script>

<style scoped>
.conversation-thread {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  min-height: min-content;
  flex-shrink: 0;
}

.cap-hint {
  margin: 0;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
</style>
