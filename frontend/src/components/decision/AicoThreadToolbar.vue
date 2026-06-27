<template>
  <div v-if="worldSession.queryMode === 'aico'" class="aico-toolbar">
    <el-button size="small" :disabled="worldSession.streamInFlight" @click="worldSession.createAicoThread()">
      {{ t('worldInteraction.decision.newConversation') }}
    </el-button>
    <el-dropdown
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
import type { AicoThread } from '@/types/world'

const { t } = useI18n()
const worldSession = useWorldSessionStore()

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
</style>
