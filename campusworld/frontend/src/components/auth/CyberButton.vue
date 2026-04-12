<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  label: string
  variant?: 'primary' | 'secondary' | 'ghost'
  loading?: boolean
  disabled?: boolean
  size?: 'default' | 'large'
}>(), {
  variant: 'primary',
  loading: false,
  disabled: false,
  size: 'default'
})

const emit = defineEmits<{
  click: [e: MouseEvent]
}>()

const buttonClasses = computed(() => ({
  'cyber-button': true,
  [`cyber-button--${props.variant}`]: true,
  [`cyber-button--${props.size}`]: true,
  'cyber-button--loading': props.loading,
  'cyber-button--disabled': props.disabled
}))

const handleClick = (e: MouseEvent) => {
  if (!props.loading && !props.disabled) {
    emit('click', e)
  }
}
</script>

<template>
  <button
    type="submit"
    :class="buttonClasses"
    :disabled="disabled || loading"
    @click="handleClick"
  >
    <span v-if="loading" class="cyber-button__spinner" />
    <span v-else class="cyber-button__content">
      <slot>{{ label }}</slot>
    </span>
  </button>
</template>

<style scoped>
.cyber-button {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-size: var(--font-size-base);
  font-weight: 500;
  letter-spacing: var(--letter-spacing-wider);
  text-transform: uppercase;
  padding: var(--spacing-md) var(--spacing-xl);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-glow);
  overflow: hidden;
  width: 100%;
}

.cyber-button--primary {
  background: linear-gradient(135deg, var(--cyber-primary-dim), transparent);
  border: 1px solid var(--cyber-primary);
  color: var(--cyber-text-bright);
  box-shadow: 0 0 10px var(--cyber-primary-dim);
}

.cyber-button--primary:hover:not(:disabled) {
  background: linear-gradient(135deg, var(--cyber-primary-glow), var(--cyber-primary-dim));
  box-shadow: var(--glow-primary);
  text-shadow: var(--glow-text);
}

.cyber-button--primary:active:not(:disabled) {
  transform: scale(0.98);
}

.cyber-button--secondary {
  background: transparent;
  border: 1px solid var(--cyber-secondary);
  color: var(--cyber-secondary);
}

.cyber-button--secondary:hover:not(:disabled) {
  border-color: var(--cyber-secondary);
  box-shadow: 0 0 15px var(--cyber-secondary-glow);
}

.cyber-button--ghost {
  background: transparent;
  border: none;
  color: var(--cyber-text-normal);
}

.cyber-button--ghost:hover:not(:disabled) {
  color: var(--cyber-primary);
  text-decoration: underline;
  text-underline-offset: 4px;
}

.cyber-button--large {
  padding: var(--spacing-lg) var(--spacing-2xl);
  font-size: var(--font-size-md);
}

.cyber-button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  filter: grayscale(0.5);
}

/* Loading state */
.cyber-button--loading {
  pointer-events: none;
}

.cyber-button__spinner {
  width: 16px;
  height: 16px;
  border: 2px solid transparent;
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.cyber-button__content {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Pulse glow animation for loading */
.cyber-button--loading::after {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: inherit;
  background: inherit;
  opacity: 0.5;
  animation: pulse-glow 1.5s ease-in-out infinite;
}

@keyframes pulse-glow {
  0%, 100% { opacity: 0.3; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(1.02); }
}

@media (prefers-reduced-motion: reduce) {
  .cyber-button__spinner,
  .cyber-button--loading::after {
    animation: none;
  }
}
</style>
