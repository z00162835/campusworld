<template>
  <section v-if="items.length" class="world-pulse" :aria-label="t('worldInteraction.quest.worldPulse.title')">
    <h4>{{ t('worldInteraction.quest.worldPulse.title') }}</h4>
    <article v-for="item in items" :key="item.id" class="world-pulse__item">
      <div>
        <strong>{{ severityLabel(item.severity) }}</strong>
        <span>{{ t(`worldInteraction.quest.worldPulse.attention.${item.attention}`) }}</span>
        <p>{{ item.assertion }}</p>
        <p v-if="item.escalation" class="world-pulse__escalation" role="status">
          <strong>{{ t('worldInteraction.quest.escalationTitle') }}</strong>
          {{ reasonLabel(item.escalation.reasonCode) }}
          <small v-if="item.escalation.correlationId"> · {{ item.escalation.correlationId }}</small>
        </p>
      </div>
      <div class="world-pulse__actions">
        <el-button v-if="item.attention === 'new'" size="small" text :disabled="busy"
          @click="$emit('attention', item.situationId, 'seen')"
        >{{ t('worldInteraction.quest.worldPulse.markSeen') }}</el-button>
        <el-button v-if="item.attention === 'snoozed'" size="small" text :disabled="busy"
          @click="$emit('attention', item.situationId, 'reset')"
        >{{ t('worldInteraction.quest.worldPulse.showNow') }}</el-button>
        <el-button v-else size="small" text :disabled="busy" @click="$emit('snooze', item.situationId)"
        >{{ t('worldInteraction.quest.worldPulse.snooze') }}</el-button>
        <el-button size="small" text :disabled="busy" @click="$emit('attention', item.situationId, 'ui_dismissed')"
        >{{ t('worldInteraction.quest.worldPulse.dismiss') }}</el-button>
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { WorldPulseItem } from '@/types/world'
defineProps<{ items: WorldPulseItem[]; busy: boolean }>()
defineEmits<{
  attention: [situationId: string, attention: 'seen' | 'reset' | 'ui_dismissed']
  snooze: [situationId: string]
}>()
const { t, te } = useI18n()
const reasonLabel = (reason: string) => {
  const key = `worldInteraction.quest.executionReason.${reason}`
  return te(key) ? t(key) : t('worldInteraction.quest.executionUnknownReason', { code: reason })
}
const severityLabel = (severity: string) => {
  const key = `worldInteraction.decision.riskLevel.${severity}`
  return te(key) ? t(key) : severity
}
</script>

<style scoped>
.world-pulse { display: grid; gap: 8px; margin-top: 10px; overflow-wrap: anywhere; }
h4 { margin: 0; }
.world-pulse__item { display: flex; justify-content: space-between; gap: 8px; padding: 8px; border-left: 3px solid var(--el-color-warning); border-radius: 6px; background: color-mix(in srgb, var(--el-color-warning) 7%, transparent); }
p { margin: 4px 0 0; }
span { margin-left: 8px; color: var(--el-text-color-secondary); }
.world-pulse__actions { display: flex; flex-wrap: wrap; align-items: center; }
@media (max-width: 640px) { .world-pulse__item { flex-direction: column; } }
</style>
