<script setup lang="ts">
withDefaults(defineProps<{
  opacity?: number
  animated?: boolean
}>(), {
  opacity: 0.03,
  animated: true
})
</script>

<template>
  <div
    class="scanline-overlay"
    :class="animated ? 'scanline-overlay--animated' : 'scanline-overlay--static'"
  />
</template>

<style scoped>
.scanline-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 2;
}

.scanline-overlay--animated {
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 0, 0, 0.15) 2px,
    rgba(0, 0, 0, 0.15) 4px
  );
  animation: scanline-scroll 8s linear infinite;
}

.scanline-overlay--static {
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 0, 0, 0.1) 2px,
    rgba(0, 0, 0, 0.1) 4px
  );
}

@keyframes scanline-scroll {
  0% { background-position: 0 0; }
  100% { background-position: 0 100vh; }
}

@media (prefers-reduced-motion: reduce) {
  .scanline-overlay--animated {
    animation: none;
  }
}
</style>
