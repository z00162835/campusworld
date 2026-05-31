import apiClient from './index'
import type { WorldSummary } from '@/types/world'

export const worldsApi = {
  getAvailable: () => apiClient.get<{ items: WorldSummary[] }>('/worlds/available'),
}
