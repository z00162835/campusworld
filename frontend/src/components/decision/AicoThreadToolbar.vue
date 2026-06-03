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
        <el-icon class="el-icon--right"><ArrowDown /></el-icon>
      </el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item
            v-for="thread in worldSession.aicoThreads"
            :key="thread.id"
            :command="thread.id"
          >
            {{ thread.title }}
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { useWorldSessionStore } from '@/stores/worldSession'

const { t } = useI18n()
const worldSession = useWorldSessionStore()

const activeTitle = computed(
  () => worldSession.aicoThreads.find(thread => thread.id === worldSession.activeAicoThreadId)?.title || 'New conversation',
)
</script>

<style scoped>
.aico-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
  padding-bottom: var(--spacing-sm);
}
</style>
