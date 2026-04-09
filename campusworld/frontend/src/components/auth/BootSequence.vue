<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'

const props = withDefaults(defineProps<{
  duration?: number
}>(), {
  duration: 2500
})

const emit = defineEmits<{
  complete: []
}>()

const stage = ref<'init' | 'logo' | 'loading' | 'ready' | 'fadeout'>('init')
const messages = ref<string[]>([])
const progress = ref(0)

const bootStages = [
  { stage: 'init', delay: 0, duration: 300 },
  { stage: 'logo', delay: 300, duration: 500, message: 'CAMPUSWORLD OS v2.4.1' },
  { stage: 'loading', delay: 800, duration: 400, message: '[INIT] Initializing system...' },
  { stage: 'loading', delay: 1200, duration: 400, message: '[KERNEL] Loading kernel modules...' },
  { stage: 'loading', delay: 1600, duration: 400, message: '[NET] Connecting to CampusWorld...' },
  { stage: 'loading', delay: 2000, duration: 400, message: '[AUTH] Authentication service ready' },
  { stage: 'ready', delay: 2400, duration: 200, message: '[SYS] Ready.' },
  { stage: 'fadeout', delay: 2600, duration: 200 }
]

const stageClass = computed(() => `boot-sequence--${stage.value}`)

onMounted(() => {
  for (const bootStage of bootStages) {
    setTimeout(() => {
      stage.value = bootStage.stage as any
      if (bootStage.message) {
        messages.value.push(bootStage.message)
      }
      // Update progress
      const stageIndex = bootStages.indexOf(bootStage)
      progress.value = Math.round(((stageIndex + 1) / bootStages.length) * 100)
    }, bootStage.delay)
  }

  // Emit complete after full duration
  setTimeout(() => {
    emit('complete')
  }, props.duration)
})
</script>

<template>
  <div class="boot-sequence" :class="stageClass">
    <!-- Background -->
    <div class="boot-sequence__bg" />

    <!-- Logo flicker -->
    <div v-if="stage === 'logo' || stage === 'loading' || stage === 'ready'" class="boot-sequence__logo">
      <span class="boot-sequence__logo-text">CAMPUSWORLD</span>
    </div>

    <!-- Loading messages -->
    <div class="boot-sequence__messages">
      <div
        v-for="(msg, index) in messages"
        :key="index"
        class="boot-sequence__message"
        :style="{ animationDelay: `${index * 0.05}s` }"
      >
        {{ msg }}
      </div>
    </div>

    <!-- Progress bar -->
    <div v-if="stage === 'loading' || stage === 'ready'" class="boot-sequence__progress">
      <div class="boot-sequence__progress-bar" :style="{ width: `${progress}%` }" />
    </div>

    <!-- Fade out overlay -->
    <div v-if="stage === 'fadeout'" class="boot-sequence__fadeout" />
  </div>
</template>

<style scoped>
.boot-sequence {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--cyber-bg-dark);
}

.boot-sequence__bg {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, var(--cyber-bg-dark) 0%, var(--cyber-bg-mid) 100%);
}

.boot-sequence__logo {
  position: relative;
  z-index: 1;
  animation: logo-flicker 0.5s ease-out;
}

.boot-sequence__logo-text {
  font-family: var(--font-display);
  font-size: 48px;
  font-weight: 700;
  letter-spacing: var(--letter-spacing-wider);
  color: var(--cyber-primary);
  text-shadow: var(--glow-text);
}

@keyframes logo-flicker {
  0% { opacity: 0; transform: scale(0.9); }
  20% { opacity: 1; transform: scale(1.02); }
  40% { opacity: 0.7; transform: scale(0.98); }
  60% { opacity: 1; transform: scale(1); }
  80% { opacity: 0.9; }
  100% { opacity: 1; }
}

.boot-sequence__messages {
  position: relative;
  z-index: 1;
  margin-top: var(--spacing-2xl);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  color: var(--cyber-text-normal);
  text-align: left;
  min-height: 120px;
}

.boot-sequence__message {
  opacity: 0;
  animation: message-appear 0.3s ease forwards;
  margin-bottom: var(--spacing-xs);
  letter-spacing: var(--letter-spacing-wide);
}

@keyframes message-appear {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.boot-sequence__progress {
  position: absolute;
  bottom: 80px;
  left: 50%;
  transform: translateX(-50%);
  width: 200px;
  height: 2px;
  background: var(--border-color);
  border-radius: 1px;
  overflow: hidden;
}

.boot-sequence__progress-bar {
  height: 100%;
  background: var(--cyber-primary);
  box-shadow: var(--glow-primary);
  transition: width 0.3s ease;
}

.boot-sequence__fadeout {
  position: absolute;
  inset: 0;
  background: var(--cyber-bg-dark);
  animation: fade-out 0.3s ease forwards;
}

@keyframes fade-out {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* Stage-specific styles */
.boot-sequence--init {
  background: #000;
}

.boot-sequence--fadeout {
  background: var(--cyber-bg-dark);
}

.boot-sequence--fadeout .boot-sequence__logo,
.boot-sequence--fadeout .boot-sequence__messages,
.boot-sequence--fadeout .boot-sequence__progress {
  animation: fade-out 0.2s ease forwards;
}

@media (prefers-reduced-motion: reduce) {
  .boot-sequence__logo,
  .boot-sequence__message,
  .boot-sequence__progress-bar,
  .boot-sequence__fadeout {
    animation: none;
  }
  .boot-sequence__message {
    opacity: 1;
  }
}
</style>
