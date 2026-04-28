import { ref, readonly } from 'vue'

export type BootStage =
  | 'idle'
  | 'initializing'
  | 'loading'
  | 'authenticating'
  | 'ready'
  | 'complete'

export interface BootSequenceState {
  stage: BootStage
  progress: number
  messages: string[]
}

export function useBootSequence() {
  const state = ref<BootSequenceState>({
    stage: 'idle',
    progress: 0,
    messages: []
  })

  const startBootSequence = async (onComplete?: () => void) => {
    state.value.stage = 'initializing'
    state.value.progress = 10
    state.value.messages = []

    const bootStages: Array<{
      stage: BootStage
      progress: number
      message: string
      delay: number
    }> = [
      { stage: 'initializing', progress: 10, message: 'Initializing system...', delay: 0 },
      { stage: 'loading', progress: 35, message: 'Loading kernel modules...', delay: 300 },
      { stage: 'loading', progress: 55, message: 'Connecting to CampusWorld...', delay: 600 },
      { stage: 'authenticating', progress: 75, message: 'Authentication service ready', delay: 900 },
      { stage: 'ready', progress: 100, message: 'System ready', delay: 1200 },
    ]

    let lastDelay = 0

    for (const bootStage of bootStages) {
      await new Promise(resolve => setTimeout(resolve, bootStage.delay - lastDelay))
      lastDelay = bootStage.delay
      state.value.stage = bootStage.stage
      state.value.progress = bootStage.progress
      state.value.messages.push(bootStage.message)
    }

    await new Promise(resolve => setTimeout(resolve, 300))
    state.value.stage = 'complete'
    onComplete?.()
  }

  const reset = () => {
    state.value = { stage: 'idle', progress: 0, messages: [] }
  }

  return {
    state: readonly(state),
    startBootSequence,
    reset
  }
}
