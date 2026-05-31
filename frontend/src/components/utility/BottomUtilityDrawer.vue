<template>
  <section class="utility-drawer" :class="{ open }">
    <button class="drawer-toggle" type="button" @click="open = !open">
      {{ t('worldInteraction.utility.toggle') }}
      <el-icon><ArrowUp v-if="!open" /><ArrowDown v-else /></el-icon>
    </button>

    <div v-if="open" class="drawer-body">
      <el-tabs v-model="activeTab">
        <el-tab-pane :label="t('worldInteraction.utility.command')" name="command">
          <div class="utility-line">
            {{ t('worldInteraction.utility.commandHint') }}
          </div>
        </el-tab-pane>
        <el-tab-pane :label="t('worldInteraction.utility.history')" name="history">
          <div v-if="!worldSession.historyItems.length" class="utility-line">
            {{ t('worldInteraction.utility.historyEmpty') }}
          </div>
          <div v-for="item in worldSession.historyItems" :key="item.id" class="history-item">
            {{ item.summary }}
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ArrowDown, ArrowUp } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { useWorldSessionStore } from '@/stores/worldSession'

const { t } = useI18n()
const worldSession = useWorldSessionStore()
const open = ref(false)
const activeTab = ref('command')
</script>

<style scoped>
.utility-drawer {
  background: #171a20;
}

.drawer-toggle {
  width: 100%;
  height: 36px;
  border: 0;
  border-top: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  cursor: pointer;
}

.drawer-body {
  height: 220px;
  overflow: auto;
  border-top: 1px solid var(--border-color);
  padding: 0 var(--spacing-lg) var(--spacing-md);
}

.utility-line,
.history-item {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  padding: var(--spacing-sm) 0;
}

.history-item {
  border-bottom: 1px solid var(--border-color-light);
}
</style>
