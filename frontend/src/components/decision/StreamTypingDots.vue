<template>
  <span class="stream-typing-dots" aria-hidden="true">
    <span class="dot" />
    <span class="dot" />
    <span class="dot" />
  </span>
</template>

<style scoped>
.stream-typing-dots {
  display: inline-flex;
  align-items: flex-end;
  gap: 3px;
  margin-left: 2px;
  height: 1em;
  vertical-align: baseline;
}

.dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.3;
  animation: stream-dot-wave 1.15s ease-in-out infinite;
}

.dot:nth-child(2) {
  animation-delay: 0.16s;
}

.dot:nth-child(3) {
  animation-delay: 0.32s;
}

@keyframes stream-dot-wave {
  0%,
  70%,
  100% {
    opacity: 0.28;
    transform: translateY(0);
  }

  35% {
    opacity: 1;
    transform: translateY(-3px);
  }
}
</style>
