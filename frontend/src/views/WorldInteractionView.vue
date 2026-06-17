<template>
  <div class="world-view">
    <entry-sequence v-if="showEntrySequence" />
    <world-shell v-else />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import EntrySequence from '@/components/game/EntrySequence.vue'
import WorldShell from '@/components/shell/WorldShell.vue'
import { useAuthStore } from '@/stores/auth'
import { useWorldSessionStore } from '@/stores/worldSession'

const authStore = useAuthStore()
const worldSession = useWorldSessionStore()
const booting = ref(true)

const showEntrySequence = computed(() => booting.value || worldSession.loading)

onMounted(async () => {
  if (!authStore.isAuthenticated) {
    const restored = await authStore.restoreSession()
    if (!restored) {
      booting.value = false
      return
    }
  }
  try {
    await worldSession.loadCurrent()
  } finally {
    booting.value = false
  }
})
</script>

<style scoped>
.world-view {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #121418;
  color: var(--text-primary);
}
</style>
