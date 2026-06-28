<template>
  <div class="query-box">
    <div v-if="showModeMenu" class="mode-menu">
      <button type="button" @click="selectMode('command')">
        <app-icon name="commandMode" :size="16" />
        <span>Command</span>
      </button>
      <button type="button" @click="selectMode('aico')">
        <app-icon name="conversation" :size="16" />
        <span>AICO</span>
      </button>
    </div>

    <div class="input-row">
      <button
        class="decision-accent-btn mode-pill"
        type="button"
        :class="{ 'mode-pill--aico': worldSession.queryMode === 'aico' }"
        :disabled="worldSession.streamInFlight"
        :aria-label="modeAriaLabel"
        :title="modeAriaLabel"
        @click="openModeMenu"
      >
        <app-icon
          :name="worldSession.queryMode === 'aico' ? 'conversation' : 'commandMode'"
          :size="16"
        />
        <span class="decision-accent-btn__label">{{ modeLabel }}</span>
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
      <button
        v-if="worldSession.streamInFlight"
        type="button"
        class="decision-accent-btn decision-accent-btn--icon-only decision-accent-btn--danger"
        :aria-label="t('worldInteraction.decision.stop')"
        :title="t('worldInteraction.decision.stop')"
        @click="stop"
      >
        <app-icon name="stop" :size="16" />
      </button>
      <button
        v-if="!worldSession.streamInFlight"
        type="button"
        class="decision-accent-btn decision-accent-btn--icon-only decision-accent-btn--primary"
        :disabled="!inputText.trim() || inputText.trim() === '/' || queryBlocked"
        :aria-label="sendAriaLabel"
        :title="sendTitle"
        @click="submit"
      >
        <app-icon
          v-if="queryBlocked"
          class="is-loading"
          name="loading"
          :size="16"
        />
        <app-icon v-else name="send" :size="16" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from '@/components/common/AppIcon.vue'
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

const queryBlocked = computed(
  () => worldSession.commandLoading || worldSession.sessionActionLoading,
)

function onEnterKeydown(event: KeyboardEvent) {
  if (event.isComposing || isComposing.value) return
  if (queryBlocked.value) return
  event.preventDefault()
  void submit()
}

const modeLabel = computed(() => worldSession.queryMode === 'aico' ? 'AICO' : 'Command')
const modeAriaLabel = computed(() =>
  worldSession.queryMode === 'aico'
    ? t('worldInteraction.decision.modeAico')
    : t('worldInteraction.decision.modeCommand'),
)
const placeholder = computed(() => worldSession.queryMode === 'aico'
  ? 'Ask AICO about the current world'
  : 'Run commands (e.g. look) or prefix search … for graph search')

const sendTitle = computed(() =>
  worldSession.streamInFlight
    ? t('worldInteraction.decision.sendAndReplace')
    : t('worldInteraction.decision.send'),
)
const sendAriaLabel = computed(() => sendTitle.value)

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
  if (queryBlocked.value) return
  const submission = await worldSession.submitQuery(clean)
  if (!submission.accepted) return
  inputText.value = ''
  showModeMenu.value = false
  await nextTick()
  emit('submitted')
  void submission.completion
}

const stop = async () => {
  await worldSession.stopStream()
}
</script>

<style scoped>
.query-box {
  position: relative;
  flex-shrink: 0;
  margin: 0 var(--spacing-sm) var(--spacing-sm);
  border: 1px solid var(--decision-fold-border);
  border-top: none;
  border-left: 3px solid var(--decision-fold-zone-header-accent);
  border-radius: 0 0 var(--radius-md) var(--radius-md);
  padding: var(--spacing-md);
  background: var(--decision-query-bg);
}

.mode-menu {
  position: absolute;
  left: var(--spacing-md);
  bottom: calc(100% - 4px);
  width: 220px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--decision-card-bg);
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
  min-width: 92px;
}

.mode-pill--aico {
  border-color: rgba(64, 158, 255, 0.45);
  color: var(--color-primary);
  background: rgba(64, 158, 255, 0.1);
}

input {
  min-width: 0;
  height: var(--decision-accent-btn-size);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: #101318;
  color: var(--text-primary);
  padding: 0 var(--spacing-md);
  outline: none;
}

input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.2);
}

.is-loading {
  animation: decision-spin 0.8s linear infinite;
}

@keyframes decision-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
