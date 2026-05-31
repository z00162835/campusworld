import { ref } from 'vue'
import { defineStore } from 'pinia'
import { commandsApi, type CommandInfo } from '@/api/commands'

export const useCommandsStore = defineStore('commands', () => {
  const commands = ref<CommandInfo[]>([])
  const loading = ref(false)

  async function loadCommands() {
    loading.value = true
    try {
      const { data } = await commandsApi.list()
      commands.value = data
    } finally {
      loading.value = false
    }
  }

  function reset() {
    commands.value = []
    loading.value = false
  }

  return {
    commands,
    loading,
    loadCommands,
    reset,
  }
})
