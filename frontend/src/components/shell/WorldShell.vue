<template>
  <div class="world-shell" :class="`mode-${worldSession.viewMode.toLowerCase()}`">
    <world-top-bar />

    <main
      ref="mainRef"
      class="world-main"
      :class="{ 'is-resizing': isResizing }"
      @keydown.esc="showMobileMap"
    >
      <section
        class="map-pane"
        :class="{ collapsed: mapCollapsed }"
        :style="mapPaneStyle"
      >
        <div v-if="mapCollapsed && !compact" class="pane-collapsed-strip">
          <button
            type="button"
            class="strip-icon-btn"
            :title="t('worldInteraction.map.expand')"
            :aria-label="t('worldInteraction.map.expand')"
            @click="mapCollapsed = false"
          >
            <app-icon name="map" :size="18" />
          </button>
        </div>
        <div v-show="!mapCollapsed || compact" class="pane-body">
          <div class="pane-collapse-row">
            <span class="pane-pane-label">
              <app-icon name="map" :size="16" />
              <span>{{ t('worldInteraction.map.title') }}</span>
            </span>
            <button
              type="button"
              class="strip-icon-btn"
              :title="t('worldInteraction.map.collapse')"
              :aria-label="t('worldInteraction.map.collapse')"
              @click="mapCollapsed = true"
            >
              <app-icon name="chevronLeft" :size="16" />
            </button>
          </div>
          <focus-semantic-map />
        </div>
      </section>

      <div
        v-if="showMapResizer"
        class="pane-resizer"
        role="separator"
        tabindex="0" aria-orientation="vertical"
        :aria-valuenow="Math.round(mapWidth)" :aria-valuemin="MAP_MIN_WIDTH"
        :aria-valuemax="maxMapWidth()"
        :aria-label="t('worldInteraction.layout.resizeMap')"
        @mousedown="startResize('map', $event)"
        @keydown="resizeWithKeyboard('map', $event)"
      />

      <decision-center-flow
        v-show="!compact || mobilePanel === 'quest'"
        id="world-quest-panel" class="decision-pane" :style="decisionPaneStyle"
        @map-locate="showMobileMap"
      />

      <div
        v-if="showContextResizer"
        class="pane-resizer"
        role="separator"
        tabindex="0" aria-orientation="vertical"
        :aria-valuenow="Math.round(contextWidth)" :aria-valuemin="CONTEXT_MIN_WIDTH"
        :aria-valuemax="maxContextWidth()"
        :aria-label="t('worldInteraction.layout.resizeContext')"
        @mousedown="startResize('context', $event)"
        @keydown="resizeWithKeyboard('context', $event)"
      />

      <section
        v-show="!compact || mobilePanel === 'clues'"
        id="world-clues-panel"
        class="context-pane"
        :class="{ collapsed: contextCollapsed }"
        :style="contextPaneStyle"
      >
        <div v-if="contextCollapsed && !compact" class="pane-collapsed-strip">
          <button
            type="button"
            class="strip-icon-btn"
            :title="t('worldInteraction.context.expand')"
            :aria-label="t('worldInteraction.context.expand')"
            @click="contextCollapsed = false"
          >
            <app-icon name="context" :size="18" />
          </button>
        </div>
        <div v-show="!contextCollapsed || compact" class="pane-body">
          <context-summary-panel @collapse="closeContext" />
        </div>
      </section>

      <div v-if="compact" class="mobile-world-hud">
        <button type="button" class="mobile-world-summary" @click="mobilePanel = 'quest'">
          <strong>{{ foregroundQuest?.title || t('worldInteraction.quest.worldPulse.title') }}</strong>
          <span v-if="foregroundObjective">{{ foregroundObjective.title }}</span>
          <span v-else-if="!foregroundQuest && firstPulse">{{ firstPulse.assertion }}</span>
        </button>
        <nav :aria-label="t('worldInteraction.quest.mobileNavigation')" class="mobile-world-nav">
          <button ref="mobileMapButton" type="button" :aria-pressed="mobilePanel === 'map'" @click="showMobileMap">
            {{ t('worldInteraction.map.title') }}
          </button>
          <button type="button" aria-controls="world-quest-panel" :aria-expanded="mobilePanel === 'quest'" @click="toggleMobilePanel('quest')">
            {{ t('worldInteraction.quest.title') }}
          </button>
          <button type="button" aria-controls="world-clues-panel" :aria-expanded="mobilePanel === 'clues'" @click="toggleMobilePanel('clues')">
            {{ t('worldInteraction.context.title') }}
          </button>
        </nav>
      </div>
    </main>

    <bottom-utility-drawer />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import AppIcon from '@/components/common/AppIcon.vue'
import { useI18n } from 'vue-i18n'
import WorldTopBar from './WorldTopBar.vue'
import FocusSemanticMap from '@/components/map/FocusSemanticMap.vue'
import DecisionCenterFlow from '@/components/decision/DecisionCenterFlow.vue'
import ContextSummaryPanel from '@/components/context/ContextSummaryPanel.vue'
import BottomUtilityDrawer from '@/components/utility/BottomUtilityDrawer.vue'
import { useWorldShellLayout } from '@/composables/useWorldShellLayout'
import { useWorldSessionStore } from '@/stores/worldSession'

const { t } = useI18n()
const worldSession = useWorldSessionStore()
const mainRef = ref<HTMLElement | null>(null)
const compact = ref(false)
const mobilePanel = ref<'map' | 'quest' | 'clues'>('map')
const mobileMapButton = ref<HTMLButtonElement | null>(null)
const foregroundQuest = computed(() => worldSession.questInteraction?.trackedQuests.find(
  quest => quest.id === worldSession.questInteraction?.foregroundQuestId,
))
const foregroundObjective = computed(() => foregroundQuest.value?.objectives.find(
  objective => objective.id === (foregroundQuest.value?.focusedObjectiveId || foregroundQuest.value?.recommendedObjectiveId),
))
const firstPulse = computed(() => worldSession.questInteraction?.worldPulse?.find(item => item.attention !== 'ui_dismissed'))
let compactMedia: MediaQueryList | undefined
function updateCompact() { compact.value = compactMedia?.matches === true }
function showMobileMap() {
  mobilePanel.value = 'map'
  if (compact.value) mobileMapButton.value?.focus()
}
function toggleMobilePanel(panel: 'quest' | 'clues') {
  mobilePanel.value = mobilePanel.value === panel ? 'map' : panel
}
function closeContext() {
  contextCollapsed.value = true
  showMobileMap()
}
onMounted(() => {
  if (typeof window.matchMedia !== 'function') return
  compactMedia = window.matchMedia('(max-width: 980px)')
  updateCompact()
  compactMedia.addEventListener('change', updateCompact)
})
onBeforeUnmount(() => compactMedia?.removeEventListener('change', updateCompact))

const {
  mapCollapsed,
  contextCollapsed,
  isResizing,
  mapPaneStyle,
  contextPaneStyle,
  decisionPaneStyle,
  showMapResizer,
  showContextResizer,
  startResize,
  resizeWithKeyboard,
  maxMapWidth,
  maxContextWidth,
  mapWidth,
  contextWidth,
  MAP_MIN_WIDTH,
  CONTEXT_MIN_WIDTH,
  applyMapCollapsedForViewMode,
} = useWorldShellLayout(mainRef, computed(() => worldSession.viewMode))

function applyShellLayoutDefaults() {
  const policy = worldSession.displayPolicy
  if (policy) {
    contextCollapsed.value = policy.contextDefaultCollapsed
  }
  applyMapCollapsedForViewMode()
}

watch(
  () => worldSession.displayPolicy,
  () => applyShellLayoutDefaults(),
  { immediate: true },
)

watch(
  () => worldSession.viewMode,
  () => applyMapCollapsedForViewMode(),
)
</script>

<style scoped>
.world-shell {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #121418;
}

.world-main {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  flex: 1;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
  background: var(--border-color-light);
  border-top: 1px solid var(--border-color);
  border-bottom: 1px solid var(--border-color);
}

.world-main.is-resizing {
  cursor: col-resize;
  user-select: none;
}

.map-pane,
.decision-pane,
.context-pane {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  background: #15181d;
  overflow: hidden;
}

.decision-pane {
  min-width: 0;
}

.decision-pane {
  overflow: hidden;
}

.decision-pane :deep(.decision-panel) {
  flex: 1;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.context-pane :deep(.context-panel) {
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.map-pane.collapsed,
.context-pane.collapsed {
  flex-shrink: 0;
}

.pane-resizer {
  flex: 0 0 6px;
  width: 6px;
  cursor: col-resize;
  background: transparent;
  position: relative;
  z-index: 2;
}

.pane-resizer::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 2px;
  width: 2px;
  background: var(--border-color);
  transition: background 0.15s ease;
}

.pane-resizer:focus-visible {
  outline: 2px solid var(--text-primary);
  outline-offset: -2px;
}

@media (prefers-reduced-motion: reduce) {
  .pane-resizer::after { transition: none; }
}

.pane-resizer:hover::after,
.world-main.is-resizing .pane-resizer::after {
  background: var(--color-primary);
}

.pane-collapsed-strip {
  height: 100%;
  min-height: 360px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md) 4px;
  border-right: 1px solid var(--border-color);
  background: #13161b;
}

.context-pane.collapsed .pane-collapsed-strip {
  border-right: 0;
  border-left: 1px solid var(--border-color);
}

.strip-label {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  letter-spacing: 0.08em;
  user-select: none;
}

.strip-icon-btn {
  border: 0;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: var(--spacing-xs);
  border-radius: var(--radius-md);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.strip-icon-btn:hover {
  color: var(--text-secondary);
  background: var(--bg-hover);
}

.strip-icon-btn:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.strip-action {
  padding: 4px;
}

.pane-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 360px;
  height: 100%;
  min-width: 0;
}

.map-pane .pane-body {
  min-height: 480px;
}

.pane-collapse-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);
  padding: 0 var(--spacing-sm);
  border-bottom: 1px solid var(--border-color-light);
  flex-shrink: 0;
}

.pane-pane-label {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  min-width: 0;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
}

@media (max-width: 980px) {
  .world-main {
    position: relative;
    min-height: 0;
    isolation: isolate;
  }

  .map-pane,
  .context-pane,
  .decision-pane {
    flex: none !important;
    width: 100% !important;
    min-width: 0 !important;
    max-width: none !important;
  }

  .pane-resizer {
    display: none;
  }

  .map-pane.collapsed,
  .context-pane.collapsed {
    width: 100% !important;
  }

  .map-pane,
  .map-pane.collapsed {
    position: absolute;
    inset: 0;
    height: 100%;
    min-height: 0;
  }

  .map-pane .pane-body {
    min-height: 0;
    padding-bottom: 7rem;
  }

  .map-pane .pane-collapse-row { display: none; }

  .decision-pane,
  .context-pane {
    position: absolute;
    inset: 0 0 auto;
    z-index: 1;
    height: calc(100% - 8rem);
    max-height: 72%;
    min-height: 0;
    border-bottom: 2px solid var(--border-color);
    box-shadow: 0 8px 24px #0008;
  }

  .context-pane .pane-body { min-height: 0; overflow-y: auto; }

  .mobile-world-hud {
    position: absolute;
    z-index: 2;
    inset: auto 0 0;
    padding: .5rem;
    padding-bottom: max(.5rem, env(safe-area-inset-bottom));
    background: #15181df5;
    border-top: 1px solid var(--border-color);
  }

  .mobile-world-summary, .mobile-world-nav button {
    color: var(--text-primary);
    background: transparent;
    font: inherit;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    min-height: 44px;
    cursor: pointer;
  }
  .mobile-world-summary {
    display: flex;
    flex-direction: column;
    width: 100%;
    text-align: start;
    padding: .25rem .5rem;
    max-height: 4rem;
    overflow-y: auto;
  }
  .mobile-world-summary strong, .mobile-world-summary span { overflow-wrap: anywhere; }
  .mobile-world-nav { display: flex; gap: .5rem; margin-top: .5rem; }
  .mobile-world-nav button { flex: 1; min-width: 0; overflow-wrap: anywhere; }
  .mobile-world-nav button[aria-expanded='true'], .mobile-world-nav button[aria-pressed='true'] {
    border-color: var(--text-primary);
    text-decoration: underline;
  }
  .mobile-world-hud button:focus-visible { outline: 2px solid var(--text-primary); outline-offset: 2px; }

  .pane-collapsed-strip {
    flex-direction: row;
    writing-mode: horizontal-tb;
    min-height: 48px;
    width: 100%;
    border-right: 0;
    border-bottom: 1px solid var(--border-color);
  }

  .strip-label {
    writing-mode: horizontal-tb;
  }
}
</style>
