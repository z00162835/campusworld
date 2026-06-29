import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { worldHistoryApi, type WorldHistoryGroup } from '@/api/worldHistory'
import { useWorldSessionStore } from '@/stores/worldSession'
import { buildCommandEntries, buildConversationEntries } from '@/utils/utilityHistory'

const ARCHIVE_PAGE_SIZE = 50
// The backend always prepends a session-derived "location" group; only merge
// archive-derived groups when appending subsequent pages.
const ARCHIVE_GROUP_IDS = new Set(['aico_conversations', 'command_conversations'])

export function useUtilityHistory() {
  const { t } = useI18n()
  const worldSession = useWorldSessionStore()
  const archivedGroups = ref<WorldHistoryGroup[]>([])
  const archivedLoaded = ref(false)
  const archivedLoading = ref(false)
  const archivedErrorKey = ref<string | null>(null)
  const archivedTotal = ref(0)
  const archivedOffset = ref(0)
  const archivedHasMore = ref(false)
  const archivedLoadingMore = ref(false)
  let refreshSeq = 0
  let refreshInFlight: Promise<void> | null = null

  const mergeGroups = (current: WorldHistoryGroup[], next: WorldHistoryGroup[]): WorldHistoryGroup[] => {
    const merged = current.map(group => ({ ...group, items: [...group.items] }))
    for (const group of next) {
      if (!ARCHIVE_GROUP_IDS.has(group.id)) continue
      const existing = merged.find(item => item.id === group.id)
      if (existing) {
        existing.items = [...existing.items, ...group.items]
      } else {
        merged.push({ ...group, items: [...group.items] })
      }
    }
    return merged
  }

  async function refreshArchivedHistory() {
    if (refreshInFlight) {
      await refreshInFlight
      return
    }

    const seq = ++refreshSeq
    archivedLoading.value = true
    archivedErrorKey.value = null
    archivedOffset.value = 0

    refreshInFlight = (async () => {
      try {
        const { data } = await worldHistoryApi.getSummary({
          limit: ARCHIVE_PAGE_SIZE,
          offset: 0,
        })
        if (seq !== refreshSeq) return
        archivedGroups.value = data.groups
        const total = data.pagination?.total ?? data.groups.reduce(
          (sum, group) => sum + group.items.length,
          0,
        )
        archivedTotal.value = total
        archivedOffset.value = ARCHIVE_PAGE_SIZE
        archivedHasMore.value = archivedOffset.value < total
      } catch (err) {
        console.warn('[useUtilityHistory] Failed to load archived history summary:', err)
        if (seq !== refreshSeq) return
        archivedErrorKey.value = 'worldInteraction.utility.historyLoadFailed'
        archivedGroups.value = []
        archivedTotal.value = 0
        archivedOffset.value = 0
        archivedHasMore.value = false
      } finally {
        if (seq === refreshSeq) {
          archivedLoading.value = false
          archivedLoaded.value = true
        }
        refreshInFlight = null
      }
    })()

    await refreshInFlight
  }

  async function loadMoreArchivedHistory() {
    if (archivedLoadingMore.value || !archivedHasMore.value) return
    const seq = ++refreshSeq
    archivedLoadingMore.value = true
    try {
      const { data } = await worldHistoryApi.getSummary({
        limit: ARCHIVE_PAGE_SIZE,
        offset: archivedOffset.value,
      })
      if (seq !== refreshSeq) return
      archivedGroups.value = mergeGroups(archivedGroups.value, data.groups)
      const total = data.pagination?.total ?? archivedTotal.value
      archivedTotal.value = total
      archivedOffset.value += ARCHIVE_PAGE_SIZE
      archivedHasMore.value = archivedOffset.value < total
    } catch (err) {
      console.warn('[useUtilityHistory] Failed to load more archived history:', err)
      if (seq !== refreshSeq) return
      archivedErrorKey.value = 'worldInteraction.utility.historyLoadFailed'
    } finally {
      if (seq === refreshSeq) {
        archivedLoadingMore.value = false
      }
    }
  }

  function resetArchivedHistory() {
    archivedGroups.value = []
    archivedLoaded.value = false
    archivedLoading.value = false
    archivedLoadingMore.value = false
    archivedErrorKey.value = null
    archivedTotal.value = 0
    archivedOffset.value = 0
    archivedHasMore.value = false
  }

  const conversationEntries = computed(() =>
    buildConversationEntries(
      worldSession.aicoThreads,
      archivedGroups.value,
      t('worldInteraction.decision.newConversation'),
    ),
  )

  const commandEntries = computed(() =>
    buildCommandEntries(
      worldSession.commandConversation,
      worldSession.historyItems,
      archivedGroups.value,
    ),
  )

  return {
    archivedLoaded,
    archivedLoading,
    archivedLoadingMore,
    archivedErrorKey,
    archivedTotal,
    archivedOffset,
    archivedHasMore,
    conversationEntries,
    commandEntries,
    refreshArchivedHistory,
    loadMoreArchivedHistory,
    resetArchivedHistory,
  }
}
