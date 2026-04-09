<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  status?: 'online' | 'offline' | 'loading'
  label?: string
}>(), {
  status: 'online',
  label: 'SYSTEM ONLINE'
})

const statusClass = computed(() => `system-status--${props.status}`)
</script>

<template>
  <div class="system-status" :class="statusClass">
    <span class="system-status__dot" />
    <span class="system-status__label">{{ label }}</span>
  </div>
</template>

<style scoped>
.system-status {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  letter-spacing: var(--letter-spacing-wide);
  text-transform: uppercase;
}

.system-status__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.system-status__label {
  color: var(--cyber-text-dim);
}

/* Online status */
.system-status--online .system-status__dot {
  background: var(--cyber-success);
  box-shadow: 0 0 8px var(--cyber-success-glow);
  animation: pulse-dot 2s ease-in-out infinite;
}

.system-status--online .system-status__label {
  color: var(--cyber-success);
}

/* Offline status */
.system-status--offline .system-status__dot {
  background: var(--cyber-danger);
  box-shadow: 0 0 8px var(--cyber-danger-glow);
}

.system-status--offline .system-status__label {
  color: var(--cyber-danger);
}

/* Loading status */
.system-status--loading .system-status__dot {
  background: var(--cyber-primary);
  box-shadow: 0 0 8px var(--cyber-primary-glow);
  animation: pulse-dot 1s ease-in-out infinite;
}

.system-status--loading .system-status__label {
  color: var(--cyber-primary);
}

@keyframes pulse-dot {
  0%, 100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.2);
    opacity: 0.7;
  }
}

@media (prefers-reduced-motion: reduce) {
  .system-status__dot {
    animation: none;
  }
}
</style>
