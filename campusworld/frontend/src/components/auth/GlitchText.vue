<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

const props = withDefaults(defineProps<{
  text: string
  tag?: string
  intensity?: 'low' | 'medium' | 'high'
  trigger?: 'hover' | 'continuous'
}>(), {
  tag: 'span',
  intensity: 'medium',
  trigger: 'hover'
})

const isActive = ref(false)

const Tag = computed(() => props.tag as any)

onMounted(() => {
  if (props.trigger === 'continuous') {
    isActive.value = true
  }
})
</script>

<template>
  <component
    :is="Tag"
    class="glitch-text"
    :class="{ 'glitch-text--active': isActive }"
    :data-text="text"
    @mouseenter="trigger === 'hover' ? isActive = true : null"
    @mouseleave="trigger === 'hover' ? isActive = false : null"
  >
    <span class="glitch-text__original">{{ text }}</span>
    <span class="glitch-text__layer glitch-text__layer--cyan">{{ text }}</span>
    <span class="glitch-text__layer glitch-text__layer--magenta">{{ text }}</span>
  </component>
</template>

<style scoped>
.glitch-text {
  position: relative;
  display: inline-block;
}

.glitch-text__original {
  position: relative;
  z-index: 1;
}

.glitch-text__layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
}

.glitch-text__layer--cyan {
  color: var(--cyber-primary);
}

.glitch-text__layer--magenta {
  color: var(--cyber-danger);
}

.glitch-text--active .glitch-text__layer--cyan {
  animation: glitch-1 0.3s infinite linear alternate-reverse;
  opacity: 0.8;
}

.glitch-text--active .glitch-text__layer--magenta {
  animation: glitch-2 0.3s infinite linear alternate-reverse;
  opacity: 0.8;
}

@keyframes glitch-1 {
  0%, 100% { clip-path: inset(40% 0 61% 0); transform: translate(-2px, 2px); }
  20% { clip-path: inset(92% 0 1% 0); transform: translate(1px, -1px); }
  40% { clip-path: inset(43% 0 1% 0); transform: translate(-1px, 2px); }
  60% { clip-path: inset(25% 0 58% 0); transform: translate(2px, -2px); }
  80% { clip-path: inset(54% 0 7% 0); transform: translate(-2px, 1px); }
}

@keyframes glitch-2 {
  0%, 100% { clip-path: inset(25% 0 58% 0); transform: translate(2px, -2px); }
  20% { clip-path: inset(54% 0 7% 0); transform: translate(-2px, 1px); }
  40% { clip-path: inset(40% 0 61% 0); transform: translate(2px, 2px); }
  60% { clip-path: inset(92% 0 1% 0); transform: translate(-1px, -1px); }
  80% { clip-path: inset(43% 0 1% 0); transform: translate(1px, 2px); }
}

@media (prefers-reduced-motion: reduce) {
  .glitch-text--active .glitch-text__layer--cyan,
  .glitch-text--active .glitch-text__layer--magenta {
    animation: none;
  }
}
</style>
