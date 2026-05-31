import apiClient from './index'

export interface CommandInfo {
  name: string
  description: string
  aliases: string[]
  command_type: string
}

export const commandsApi = {
  list: () => apiClient.get<CommandInfo[]>('/command/'),
  execute: (command: string) => apiClient.post<{ success: boolean; message: string; data?: Record<string, unknown>; should_exit: boolean }>('/command/execute', { command }),
}
