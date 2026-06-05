<template>
  <div class="world-shell" :class="`mode-${worldSession.viewMode.toLowerCase()}`">
    <world-top-bar />

    <main
      ref="mainRef"
      class="world-main"
      :class="{ 'is-resizing': isResizing }"
    >
      <section
        class="map-pane"
        :class="{ collapsed: mapCollapsed }"
        :style="mapPaneStyle"
      >
        <div v-if="mapCollapsed" class="pane-collapsed-strip">
          <span class="strip-label">{{ t('worldInteraction.map.title') }}</span>
          <el-button
            class="strip-action"
            size="small"
            text
            :title="t('worldInteraction.map.expand')"
            @click="mapCollapsed = false"
          >
            <el-icon><DArrowRight /></el-icon>
          </el-button>
        </div>
        <div v-show="!mapCollapsed" class="pane-body">
          <div class="pane-collapse-row">
            <el-button size="small" text @click="mapCollapsed = true">
              {{ t('worldInteraction.map.collapse') }}
            </el-button>
          </div>
          <focus-semantic-map />
        </div>
      </section>

      <div
        v-if="showMapResizer"
        class="pane-resizer"
        role="separator"
        :aria-label="t('worldInteraction.layout.resizeMap')"
        @mousedown="startResize('map', $event)"
      />

      <decision-center-flow class="decision-pane" :style="decisionPaneStyle" />

      <div
        v-if="showContextResizer"
        class="pane-resizer"
        role="separator"
        :aria-label="t('worldInteraction.layout.resizeContext')"
        @mousedown="startResize('context', $event)"
      />

      <section
        class="context-pane"
        :class="{ collapsed: contextCollapsed }"
        :style="contextPaneStyle"
      >
        <div v-if="contextCollapsed" class="pane-collapsed-strip">
          <span class="strip-label">{{ t('worldInteraction.context.title') }}</span>
          <el-button
            class="strip-action"
            size="small"
            text
            :title="t('worldInteraction.context.expand')"
            @click="contextCollapsed = false"
          >
            <el-icon><DArrowLeft /></el-icon>
          </el-button>
        </div>
        <div v-show="!contextCollapsed" class="pane-body">
          <context-summary-panel @collapse="contextCollapsed = true" />
        </div>
      </section>
    </main>

    <bottom-utility-drawer />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { DArrowLeft, DArrowRight } from '@element-plus/icons-vue'
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
  justify-content: flex-start;
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
  justify-content: flex-end;
  padding: 0 var(--spacing-sm);
  border-bottom: 1px solid var(--border-color-light);
  flex-shrink: 0;
}

@media (max-width: 980px) {
  .world-main {
    flex-direction: column;
    min-height: auto;
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
    min-height: 48px;
  }

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
