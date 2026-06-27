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

  async function refreshArchivedHistory() {
    try {
      const { data } = await worldHistoryApi.getSummary()
      archivedGroups.value = data.groups
    } catch (err) {
      console.warn('[useUtilityHistory] Failed to load archived history summary:', err)
      archivedGroups.value = []
    } finally {
      archivedLoaded.value = true
    }
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
    conversationEntries,
    commandEntries,
    refreshArchivedHistory,
  }
}
