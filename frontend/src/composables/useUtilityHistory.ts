import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { worldHistoryApi, type WorldHistoryGroup } from '@/api/worldHistory'
import { useWorldSessionStore } from '@/stores/worldSession'
import { buildCommandEntries, buildConversationEntries } from '@/utils/utilityHistory'

export function useUtilityHistory() {
  const { t } = useI18n()
  const worldSession = useWorldSessionStore()
  const archivedGroups = ref<WorldHistoryGroup[]>([])
  const archivedLoaded = ref(false)
  const archivedLoading = ref(false)
  const archivedErrorKey = ref<string | null>(null)
  let refreshSeq = 0
  let refreshInFlight: Promise<void> | null = null

  async function refreshArchivedHistory() {
    if (refreshInFlight) {
      await refreshInFlight
      return
    }

    const seq = ++refreshSeq
    archivedLoading.value = true
    archivedErrorKey.value = null

    refreshInFlight = (async () => {
      try {
        const { data } = await worldHistoryApi.getSummary()
        if (seq !== refreshSeq) return
        archivedGroups.value = data.groups
      } catch (err) {
        console.warn('[useUtilityHistory] Failed to load archived history summary:', err)
        if (seq !== refreshSeq) return
        archivedErrorKey.value = 'worldInteraction.utility.historyLoadFailed'
        archivedGroups.value = []
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
    archivedErrorKey,
    conversationEntries,
    commandEntries,
    refreshArchivedHistory,
  }
}
