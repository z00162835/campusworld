<template>
<div class="companion-encounter">
      <div class="companion-avatar" aria-hidden="true">AI</div>
      <div class="companion-dialogue">
        <span>{{ companionName || t('worldInteraction.quest.aicoFallback') }}</span>
        <p>{{ t('worldInteraction.decision.companionPrompt') }}</p>
        <div class="dialogue-choices">
          <button
            type="button"
            :disabled="busy"
            @click="$emit('ask', 'next_step')"
          >
            {{ t('worldInteraction.decision.questHelp.nextStep') }}
          </button>
          <button
            type="button"
            :disabled="busy"
            @click="$emit('ask', 'explain_basis')"
          >
            {{ t('worldInteraction.decision.questHelp.explainBasis') }}
          </button>
        </div>
      </div>
    </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
defineProps<{ companionName?: string; busy: boolean }>()
defineEmits<{ ask: [intent: 'next_step' | 'explain_basis'] }>()
const { t } = useI18n()
</script>

<style scoped>
.companion-encounter {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  gap: var(--spacing-sm);
  margin: var(--spacing-md) 0;
  padding: var(--spacing-sm);
  border: 1px solid rgba(64, 158, 255, 0.25);
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, rgba(64, 158, 255, 0.08), transparent);
}

.companion-avatar {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(64, 158, 255, 0.5);
  border-radius: 50%;
  color: var(--color-primary);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-bold);
}

.companion-dialogue > span {
  color: var(--color-primary);
  font-size: var(--font-size-xs);
}

.companion-dialogue p {
  margin: 2px 0 var(--spacing-sm);
}

.dialogue-choices {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.dialogue-choices button {
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-secondary);
  padding: 4px 10px;
  cursor: pointer;
}

.dialogue-choices button:hover:not(:disabled),
.dialogue-choices button:focus-visible {
  border-color: var(--color-primary);
  color: var(--text-primary);
}

.dialogue-choices button:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }
</style>
