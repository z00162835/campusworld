<template>
  <div class="query-box">
    <div v-if="showModeMenu" class="mode-menu">
      <button type="button" @click="selectMode('command')">
        <el-icon><Monitor /></el-icon>
        <span>Command</span>
      </button>
      <button type="button" @click="selectMode('aico')">
        <el-icon><ChatRound /></el-icon>
        <span>AICO</span>
      </button>
    </div>

    <div class="input-row">
      <button
        class="mode-pill"
        type="button"
        :disabled="worldSession.streamInFlight"
        @click="openModeMenu"
      >
        {{ modeLabel }}
      </button>
      <input
        ref="inputRef"
        v-model="inputText"
        :placeholder="placeholder"
        @input="handleInput"
        @compositionstart="isComposing = true"
        @compositionend="isComposing = false"
        @keydown.enter="onEnterKeydown"
        @keydown.esc="showModeMenu = false"
      />
      <el-button
        v-if="worldSession.streamInFlight"
        type="danger"
        size="small"
        @click="stop"
      >
        {{ t('worldInteraction.decision.stop') }}
      </el-button>
      <el-button
        v-else
        type="primary"
        size="small"
        :loading="worldSession.actionLoading"
        :disabled="!inputText.trim() || inputText.trim() === '/'"
        @click="submit"
      >
        Send
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { ChatRound, Monitor } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { useWorldSessionStore } from '@/stores/worldSession'
import type { QueryMode } from '@/types/world'

const emit = defineEmits<{ submitted: [] }>()

const { t } = useI18n()
const worldSession = useWorldSessionStore()
const inputText = ref('')
const showModeMenu = ref(false)
const inputRef = ref<HTMLInputElement>()
/** IME composition in progress; Enter confirms candidates, must not submit. */
const isComposing = ref(false)

function onEnterKeydown(event: KeyboardEvent) {
  if (event.isComposing || isComposing.value) return
  event.preventDefault()
  void submit()
}

const modeLabel = computed(() => worldSession.queryMode === 'aico' ? 'AICO' : 'Command')
const placeholder = computed(() => worldSession.queryMode === 'aico'
  ? 'Ask AICO about the current world'
  : 'Run commands (e.g. look) or prefix search … for graph search')

const handleInput = () => {
  showModeMenu.value = inputText.value.trim() === '/'
}

const openModeMenu = async () => {
  if (worldSession.streamInFlight) return
  showModeMenu.value = true
  await nextTick()
  inputRef.value?.focus()
}

const selectMode = async (mode: QueryMode) => {
  worldSession.setQueryMode(mode)
  showModeMenu.value = false
  if (inputText.value.trim() === '/') inputText.value = ''
  await nextTick()
  inputRef.value?.focus()
}

const submit = async () => {
  const clean = inputText.value.trim()
  if (!clean || clean === '/') return
  inputText.value = ''
  showModeMenu.value = false
  await worldSession.submitQuery(clean)
  emit('submitted')
}

const stop = async () => {
  await worldSession.stopStream()
}
</script>

<style scoped>
.query-box {
  position: relative;
  flex-shrink: 0;
  border-top: 1px solid var(--border-color);
  padding: var(--spacing-md);
  background: #171a20;
}

.mode-menu {
  position: absolute;
  left: var(--spacing-md);
  bottom: calc(100% - 4px);
  width: 220px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: #20252d;
  box-shadow: var(--shadow-lg);
  padding: var(--spacing-sm);
  z-index: 3;
}

.mode-menu button {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  border: 0;
  background: transparent;
  color: var(--text-primary);
  padding: var(--spacing-sm);
  border-radius: var(--radius-md);
  cursor: pointer;
}

.mode-menu button:hover {
  background: var(--bg-hover);
}

.input-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: var(--spacing-sm);
  align-items: center;
}

.mode-pill {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: #20252d;
  color: var(--text-secondary);
  padding: 7px 9px;
  cursor: pointer;
  min-width: 84px;
}

input {
  min-width: 0;
  height: 34px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: #101318;
  color: var(--text-primary);
  padding: 0 var(--spacing-md);
  outline: none;
}

input:focus {
  border-color: var(--color-primary);
}
</style>
