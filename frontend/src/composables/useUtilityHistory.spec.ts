import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useUtilityHistory } from './useUtilityHistory'
import { worldHistoryApi } from '@/api/worldHistory'

vi.mock('@/api/worldHistory', () => ({
  worldHistoryApi: {
    getSummary: vi.fn(),
  },
}))

vi.mock('@/stores/worldSession', () => ({
  useWorldSessionStore: () => ({
    aicoThreads: [],
    commandConversation: [],
    historyItems: [],
  }),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

function archiveGroup(id: string, items: Array<{ id: string; title: string; messageCount: number; preview: string; createdAt: string }>) {
  return { id, title: id, items }
}

function summaryResponse(total: number, offset: number, limit: number, aicoItems: any[], commandItems: any[] = []) {
  const groups = [
    archiveGroup('location', [{ id: 'loc', title: 'Loc', messageCount: 1, preview: '', createdAt: '2026-06-01T00:00:00.000Z' }]),
  ]
  if (aicoItems.length) groups.push(archiveGroup('aico_conversations', aicoItems))
  if (commandItems.length) groups.push(archiveGroup('command_conversations', commandItems))
  return {
    data: {
      groups,
      collapsed: true,
      pagination: { limit, offset, total },
    },
  }
}

describe('useUtilityHistory pagination', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('requests the first page with limit/offset and exposes hasMore', async () => {
    vi.mocked(worldHistoryApi.getSummary).mockResolvedValueOnce(
      summaryResponse(120, 0, 50, [
        { id: 'a1', title: 'A1', messageCount: 1, preview: 'p', createdAt: '2026-06-01T00:00:00.000Z' },
      ]) as any,
    )

    const { refreshArchivedHistory, archivedHasMore, archivedTotal, archivedOffset } = useUtilityHistory()
    await refreshArchivedHistory()

    expect(worldHistoryApi.getSummary).toHaveBeenCalledWith({ limit: 50, offset: 0 })
    expect(archivedHasMore.value).toBe(true)
    expect(archivedTotal.value).toBe(120)
    expect(archivedOffset.value).toBe(50)
  })

  it('appends archive-derived groups on loadMore and stops when offset reaches total', async () => {
    vi.mocked(worldHistoryApi.getSummary)
      .mockResolvedValueOnce(
        summaryResponse(60, 0, 50, [
          { id: 'a1', title: 'A1', messageCount: 1, preview: 'p', createdAt: '2026-06-01T00:00:00.000Z' },
        ]) as any,
      )
      .mockResolvedValueOnce(
        summaryResponse(60, 50, 50, [
          { id: 'a2', title: 'A2', messageCount: 1, preview: 'p', createdAt: '2026-06-02T00:00:00.000Z' },
        ]) as any,
      )

    const {
      refreshArchivedHistory,
      loadMoreArchivedHistory,
      conversationEntries,
      archivedHasMore,
    } = useUtilityHistory()

    await refreshArchivedHistory()
    expect(archivedHasMore.value).toBe(true)

    await loadMoreArchivedHistory()
    expect(worldHistoryApi.getSummary).toHaveBeenLastCalledWith({ limit: 50, offset: 50 })
    expect(archivedHasMore.value).toBe(false)
    const ids = conversationEntries.value.map(entry => entry.id)
    expect(ids).toContain('a1')
    expect(ids).toContain('a2')
  })

  it('does not duplicate the location group across pages', async () => {
    vi.mocked(worldHistoryApi.getSummary)
      .mockResolvedValueOnce(
        summaryResponse(60, 0, 50, [
          { id: 'a1', title: 'A1', messageCount: 1, preview: 'p', createdAt: '2026-06-01T00:00:00.000Z' },
        ]) as any,
      )
      .mockResolvedValueOnce(
        summaryResponse(60, 50, 50, [
          { id: 'a2', title: 'A2', messageCount: 1, preview: 'p', createdAt: '2026-06-02T00:00:00.000Z' },
        ]) as any,
      )

    const { refreshArchivedHistory, loadMoreArchivedHistory, commandEntries } = useUtilityHistory()
    await refreshArchivedHistory()
    await loadMoreArchivedHistory()

    // location group is session-derived and filtered out of command entries;
    // no duplicate command items from the repeated location group.
    expect(commandEntries.value).toHaveLength(0)
  })
})
