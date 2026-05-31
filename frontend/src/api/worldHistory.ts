import apiClient from './index'

export interface WorldHistoryGroup {
  id: string
  title: string
  items: Array<{ id: string; summary: string; createdAt: string }>
}

export const worldHistoryApi = {
  getSummary: () => apiClient.get<{ groups: WorldHistoryGroup[]; collapsed: boolean }>('/world-history/summary'),
}
