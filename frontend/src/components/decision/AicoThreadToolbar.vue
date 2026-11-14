<template>
  <div v-if="worldSession.queryMode === 'aico'" class="aico-toolbar">
    <span v-if="activeQuest" class="quest-guide-label">
      {{ t('worldInteraction.decision.questGuide', { title: activeQuest.questTitle || activeQuest.title }) }}
    </span>
    <el-button v-else size="small" :disabled="worldSession.streamInFlight" @click="worldSession.createAicoThread()">
      {{ t('worldInteraction.decision.newConversation') }}
    </el-button>
    <el-dropdown
      v-if="!activeQuest"
      trigger="click"
      popper-class="cw-dropdown-popper"
      :disabled="worldSession.streamInFlight"
      @command="worldSession.setActiveAicoThread"
    >
      <el-button size="small" :disabled="worldSession.streamInFlight">
        {{ t('worldInteraction.decision.currentConversation', { title: activeTitle }) }}
        <app-icon class="toolbar-chevron" name="chevronDown" :size="12" />
      </el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item
            v-for="thread in worldSession.aicoThreads"
            :key="thread.id"
            :command="thread.id"
          >
            {{ getThreadTitle(thread) }}
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppIcon from '@/components/common/AppIcon.vue'
import { useI18n } from 'vue-i18n'
import { useWorldSessionStore } from '@/stores/worldSession'
import { useDecisionCenterStore } from '@/stores/decisionCenter'
import type { AicoThread } from '@/types/world'

const { t } = useI18n()
const worldSession = useWorldSessionStore()
const decisionStore = useDecisionCenterStore()
const activeQuest = computed(() => decisionStore.activeTask?.questId ? decisionStore.activeTask : null)

const getThreadTitle = (thread: AicoThread) => thread.title || (thread.titleKey ? t(thread.titleKey) : '')

const activeTitle = computed(
  () => {
    const thread = worldSession.aicoThreads.find(row => row.id === worldSession.activeAicoThreadId)
    return thread ? getThreadTitle(thread) : t('worldInteraction.decision.newConversation')
  },
)
</script>

<style scoped>
.aico-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}

.toolbar-chevron {
  margin-left: var(--spacing-xs);
}

.quest-guide-label {
  color: var(--color-primary);
  font-size: var(--font-size-sm);
}
</style>
