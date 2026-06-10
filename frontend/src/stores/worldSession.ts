import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import i18n from '@/locales'
import { worldSessionsApi, type ActionResponse } from '@/api/worldSessions'
import { decisionCenterApi, queryAicoStream } from '@/api/decisionCenter'
import { buildArchivePayload, worldHistoryApi } from '@/api/worldHistory'
import { useWorldMapStore } from './worldMap'
import type {
  AicoThread,
  ConversationMessage,
  DisplayPolicy,
  QueryMode,
  StatePatch,
  ViewMode,
  WorldInteractionState,
  WorldSummary,
} from '@/types/world'

const CONVERSATION_CAP = 50
const NEW_CONVERSATION_TITLE_KEY = 'worldInteraction.decision.newConversation'
const LOAD_FAILED_KEY = 'worldInteraction.decision.loadFailed'
const STREAM_FAILED_KEY = 'worldInteraction.decision.streamFailed'

function newId(): string {
  return `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

function trimMessages(messages: ConversationMessage[]): ConversationMessage[] {
  if (messages.length <= CONVERSATION_CAP) return messages
  return messages.slice(messages.length - CONVERSATION_CAP)
}

function threadTitleFromQuery(query: string): string {
  const clean = query.trim()
  return clean.length > 32 ? `${clean.slice(0, 32)}…` : clean
}

export const useWorldSessionStore = defineStore('worldSession', () => {
  const interactionState = ref<WorldInteractionState | null>(null)
  const displayPolicy = ref<DisplayPolicy | null>(null)
  const availableWorlds = ref<WorldSummary[]>([])
  const loading = ref(false)
  const actionLoading = ref(false)
  const error = ref<string | null>(null)
  const errorKey = ref<string | null>(null)
  const viewMode = ref<ViewMode>('Focus')
  const queryMode = ref<QueryMode>('aico')
  const historyItems = ref<Array<{ id: string; summary: string; createdAt: string }>>([])

  const commandConversation = ref<ConversationMessage[]>([])
  const aicoThreads = ref<AicoThread[]>([])
  const activeAicoThreadId = ref<string | null>(null)

  const activeStreamId = ref<string | null>(null)
  let streamGeneration = 0
  let streamAbort: AbortController | null = null
  let streamAssistantId: string | null = null
  let streamThreadId: string | null = null
  let pendingStreamDelta = ''
  let streamFlushTimer: ReturnType<typeof setTimeout> | null = null
  const STREAM_FLUSH_MIN_CHARS = 32
  const STREAM_FLUSH_MS = 16

  const session = computed(() => interactionState.value?.session || null)
  const decisionCenter = computed(() => interactionState.value?.decision_center || null)
  const focusMap = computed(() => interactionState.value?.focus_map || null)
  const contextSummary = computed(() => interactionState.value?.context_summary || null)
  const currentWorld = computed(() => availableWorlds.value.find(world => world.is_current) || null)

  const activeAicoThread = computed(() =>
    aicoThreads.value.find(thread => thread.id === activeAicoThreadId.value) || null,
  )

  const conversationMessages = computed(() =>
    queryMode.value === 'aico' ? activeAicoThread.value?.messages ?? [] : commandConversation.value,
  )

  const conversationAtCap = computed(() => conversationMessages.value.length >= CONVERSATION_CAP)
  const streamInFlight = computed(() => actionLoading.value && queryMode.value === 'aico')

  function ensureActiveAicoThread(): AicoThread {
    let thread = activeAicoThread.value
    if (!thread) {
      thread = createAicoThread()
    }
    return thread
  }

  function createAicoThread(): AicoThread {
    if (streamInFlight.value) {
      ElMessage.warning(i18n.global.t('worldInteraction.decision.streamSwitchBlocked'))
      return ensureActiveAicoThread()
    }
    const thread: AicoThread = {
      id: newId(),
      titleKey: NEW_CONVERSATION_TITLE_KEY,
      messages: [],
      updatedAt: new Date().toISOString(),
    }
    aicoThreads.value = [thread, ...aicoThreads.value]
    activeAicoThreadId.value = thread.id
    return thread
  }

  function setActiveAicoThread(threadId: string) {
    if (streamInFlight.value && threadId !== activeAicoThreadId.value) {
      ElMessage.warning(i18n.global.t('worldInteraction.decision.streamSwitchBlocked'))
      return
    }
    if (aicoThreads.value.some(thread => thread.id === threadId)) {
      activeAicoThreadId.value = threadId
    }
  }

  function toggleMessageExpanded(messageId: string) {
    const list =
      queryMode.value === 'aico' ? ensureActiveAicoThread().messages : commandConversation.value
    const row = list.find(msg => msg.id === messageId)
    if (row) row.expanded = !row.expanded
  }

  function appendMessage(message: ConversationMessage) {
    if (queryMode.value === 'aico') {
      const thread = ensureActiveAicoThread()
      if (message.role === 'user' && thread.titleKey === NEW_CONVERSATION_TITLE_KEY) {
        thread.title = threadTitleFromQuery(message.query || message.answer)
        thread.titleKey = undefined
      }
      thread.messages = trimMessages([...thread.messages, message])
      thread.updatedAt = new Date().toISOString()
    } else {
      commandConversation.value = trimMessages([...commandConversation.value, message])
    }
  }

  function clearActiveAicoThreads() {
    aicoThreads.value = []
    activeAicoThreadId.value = null
  }

  function clearLocalConversations() {
    clearActiveAicoThreads()
    commandConversation.value = []
  }

  async function loadCurrent() {
    loading.value = true
    error.value = null
    errorKey.value = null
    try {
      const { data } = await worldSessionsApi.getCurrent()
      interactionState.value = data.interaction_state
      displayPolicy.value = data.display_policy
      availableWorlds.value = data.available_worlds
      useWorldMapStore().clearMapSelection()
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      if (typeof detail === 'string') {
        error.value = detail
      } else if (Array.isArray(detail)) {
        const detailText = detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join('; ')
        if (detailText) {
          error.value = detailText
        } else {
          errorKey.value = LOAD_FAILED_KEY
        }
      } else {
        error.value = err?.message || null
        errorKey.value = err?.message ? null : LOAD_FAILED_KEY
      }
    } finally {
      loading.value = false
    }
  }

  async function refreshInteractionState() {
    if (!session.value?.id) {
      await loadCurrent()
      return
    }
    const { data } = await worldSessionsApi.getInteractionState(session.value.id)
    interactionState.value = data
  }

  async function enterWorld(worldId: string) {
    const { data } = await runAction(() => worldSessionsApi.enterWorld(worldId))
    await applyActionResponse(data)
    clearActiveAicoThreads()
    await loadCurrent()
  }

  async function leaveWorld() {
    const { data } = await runAction(() => worldSessionsApi.leaveWorld())
    await applyActionResponse(data)
    clearActiveAicoThreads()
    await loadCurrent()
  }

  async function executeDecisionAction(decisionEventId: string, optionId: string) {
    if (!session.value?.id) return
    const { data } = await runAction(() => decisionCenterApi.executeAction(session.value!.id, decisionEventId, optionId))
    await applyActionResponse(data)
    await loadCurrent()
  }

  async function submitQuery(query: string) {
    if (!session.value?.id) return
    const clean = query.trim()
    if (!clean) return

    if (queryMode.value === 'aico' && streamInFlight.value) {
      await stopStream({ handoff: true })
    }

    appendMessage({
      id: newId(),
      role: 'user',
      mode: queryMode.value,
      query: clean,
      answer: clean,
    })

    if (queryMode.value === 'aico') {
      await submitAicoStream(clean)
      return
    }

    actionLoading.value = true
    try {
      const { data } = await decisionCenterApi.query(session.value.id, clean, 'command')
      appendMessage({
        id: newId(),
        role: 'assistant',
        mode: 'command',
        query: clean,
        answer: data.answer || data.command_result?.message || '',
        results: data.results,
        commandResult: data.command_result,
      })
      if (data.state_patch) {
        await applyStatePatch(data.state_patch)
        await refreshInteractionState()
      }
    } catch (err: any) {
      ElMessage.error(err?.response?.data?.detail || err?.message || i18n.global.t('worldInteraction.decision.queryFailed'))
    } finally {
      actionLoading.value = false
    }
  }

  function mapActivityToStatusKey(activity?: string, detail?: string): string | null {
    if (!activity) return null
    if (activity === 'working') return detail === 'finalizing' ? 'generating' : 'working'
    if (activity === 'tool') return 'executing'
    if (activity === 'writing') return 'generating'
    if (activity === 'rewrite') return 'rewriting'
    return 'working'
  }

  function mapTickPhaseToStatusKey(phase?: string, clientHint?: string): string | null {
    if (phase === 'complete') return null
    if (phase === 'start') return clientHint ? 'working' : 'working'
    return null
  }

  function threadForStream(threadId: string | null): AicoThread | undefined {
    if (!threadId) return undefined
    return aicoThreads.value.find(thread => thread.id === threadId)
  }

  function patchStreamAssistant(
    assistantId: string,
    threadId: string,
    patch: Partial<ConversationMessage>,
  ) {
    const thread = threadForStream(threadId)
    if (!thread) return
    const idx = thread.messages.findIndex(msg => msg.id === assistantId)
    if (idx < 0) return
    thread.messages[idx] = { ...thread.messages[idx], ...patch }
    thread.updatedAt = new Date().toISOString()
  }

  function flushPendingStreamDelta(assistantId: string, threadId: string) {
    if (!pendingStreamDelta) return
    const chunk = pendingStreamDelta
    pendingStreamDelta = ''
    const thread = threadForStream(threadId)
    if (!thread) return
    const idx = thread.messages.findIndex(msg => msg.id === assistantId)
    if (idx < 0) return
    const row = thread.messages[idx]
    thread.messages[idx] = { ...row, answer: `${row.answer || ''}${chunk}` }
  }

  function scheduleStreamDeltaFlush(assistantId: string, threadId: string) {
    if (pendingStreamDelta.length >= STREAM_FLUSH_MIN_CHARS) {
      if (streamFlushTimer != null) {
        clearTimeout(streamFlushTimer)
        streamFlushTimer = null
      }
      flushPendingStreamDelta(assistantId, threadId)
      return
    }
    if (streamFlushTimer != null) return
    streamFlushTimer = setTimeout(() => {
      streamFlushTimer = null
      flushPendingStreamDelta(assistantId, threadId)
    }, STREAM_FLUSH_MS)
  }

  async function submitAicoStream(query: string) {
    if (!session.value?.id) return
    const generation = ++streamGeneration
    const thread = ensureActiveAicoThread()
    const threadId = thread.id

    const assistantId = newId()
    streamAssistantId = assistantId
    streamThreadId = threadId
    appendMessage({
      id: assistantId,
      role: 'assistant',
      mode: 'aico',
      query,
      answer: '',
      streaming: true,
      streamStatusKey: 'working',
    })

    streamAbort = new AbortController()
    actionLoading.value = true
    activeStreamId.value = null

    try {
      await queryAicoStream(session.value.id, query, {
        threadId,
        signal: streamAbort.signal,
        onEvent: event => {
          if (generation !== streamGeneration) return
          if (event.kind === 'meta' && event.stream_id) {
            activeStreamId.value = event.stream_id
            return
          }
          if (event.kind === 'meta' && event.scope === 'activity') {
            if (event.activity === 'rewrite') {
              flushPendingStreamDelta(assistantId, threadId)
              pendingStreamDelta = ''
              patchStreamAssistant(assistantId, threadId, { answer: '' })
            }
            const actKey = mapActivityToStatusKey(event.activity, event.detail)
            if (actKey !== null) {
              patchStreamAssistant(assistantId, threadId, { streamStatusKey: actKey })
            }
            return
          }
          if (event.kind === 'meta' && event.scope === 'tick') {
            const key = mapTickPhaseToStatusKey(event.phase, event.client_hint)
            if (key !== null) {
              patchStreamAssistant(assistantId, threadId, { streamStatusKey: key })
            }
            if (event.phase === 'complete') {
              patchStreamAssistant(assistantId, threadId, { streamStatusKey: null })
            }
            return
          }
          if (event.kind === 'delta' && event.text) {
            pendingStreamDelta += event.text
            scheduleStreamDeltaFlush(assistantId, threadId)
            return
          }
          if (event.kind === 'end') {
            flushPendingStreamDelta(assistantId, threadId)
            patchStreamAssistant(assistantId, threadId, {
              answer: event.full_text || undefined,
              streaming: false,
              streamStatusKey: null,
            })
            return
          }
          if (event.kind === 'state_patch' && event.state_patch) {
            flushPendingStreamDelta(assistantId, threadId)
            void applyStatePatch(event.state_patch)
              .then(() => refreshInteractionState())
              .catch(err => {
                console.warn('[worldSession] state_patch apply failed:', err)
              })
          }
          if (event.kind === 'cancelled') {
            flushPendingStreamDelta(assistantId, threadId)
            patchStreamAssistant(assistantId, threadId, {
              streaming: false,
              cancelled: true,
              streamStatusKey: null,
            })
          }
          if (event.kind === 'error') {
            flushPendingStreamDelta(assistantId, threadId)
            const answerKey =
              event.code === 'llm_timeout'
                ? 'worldInteraction.decision.llmTimeout'
                : event.code === 'draft_incomplete'
                  ? 'worldInteraction.decision.draftIncomplete'
                  : event.message
                    ? null
                    : STREAM_FAILED_KEY
            patchStreamAssistant(assistantId, threadId, {
              streaming: false,
              answer: event.message || '',
              answerKey,
              streamStatusKey: null,
            })
          }
        },
      })
      flushPendingStreamDelta(assistantId, threadId)
      patchStreamAssistant(assistantId, threadId, { streaming: false, streamStatusKey: null })
    } catch (err: any) {
      if (generation !== streamGeneration) return
      if (err?.name === 'AbortError') {
        patchStreamAssistant(assistantId, threadId, {
          streaming: false,
          cancelled: true,
          streamStatusKey: null,
        })
      } else {
        patchStreamAssistant(assistantId, threadId, {
          streaming: false,
          answer: err?.message || '',
          answerKey: err?.message ? null : STREAM_FAILED_KEY,
          streamStatusKey: null,
        })
        ElMessage.error(err?.message || i18n.global.t('worldInteraction.decision.streamFailed'))
      }
    } finally {
      if (generation !== streamGeneration) return
      actionLoading.value = false
      streamAbort = null
      streamAssistantId = null
      streamThreadId = null
      activeStreamId.value = null
      pendingStreamDelta = ''
      if (streamFlushTimer != null) {
        clearTimeout(streamFlushTimer)
        streamFlushTimer = null
      }
    }
  }

  async function stopStream(options?: { handoff?: boolean }) {
    const handoff = options?.handoff ?? false
    const assistantId = streamAssistantId
    const threadId = streamThreadId
    streamGeneration += 1
    streamAbort?.abort()
    const streamId = activeStreamId.value
    if (streamId) {
      try {
        await decisionCenterApi.cancelStream(streamId)
      } catch (err) {
        console.warn('Failed to cancel AICO stream on server', err)
      }
    }
    if (assistantId && threadId) {
      patchStreamAssistant(assistantId, threadId, {
        streaming: false,
        cancelled: true,
        streamStatusKey: null,
      })
    }
    if (!handoff) {
      actionLoading.value = false
      streamAbort = null
      streamAssistantId = null
      streamThreadId = null
      activeStreamId.value = null
      pendingStreamDelta = ''
      if (streamFlushTimer != null) {
        clearTimeout(streamFlushTimer)
        streamFlushTimer = null
      }
    }
  }

  function cleanupActiveStream(options: { cancelServerStream?: boolean } = {}) {
    const cancelServerStream = options.cancelServerStream !== false
    streamGeneration += 1
    streamAbort?.abort()
    const streamId = activeStreamId.value
    if (cancelServerStream && streamId) {
      void decisionCenterApi.cancelStream(streamId).catch(err => {
        console.warn('Failed to cancel AICO stream on server', err)
      })
    }
    streamAbort = null
    streamAssistantId = null
    streamThreadId = null
    activeStreamId.value = null
    pendingStreamDelta = ''
    if (streamFlushTimer != null) {
      clearTimeout(streamFlushTimer)
      streamFlushTimer = null
    }
  }

  async function archiveConversations(): Promise<void> {
    const payload = buildArchivePayload(aicoThreads.value, commandConversation.value)
    const hasContent = payload.aico_threads.length > 0 || payload.command_conversation.length > 0
    if (!hasContent) return
    try {
      await worldHistoryApi.archiveConversations(payload)
    } catch (err) {
      console.warn('Failed to archive conversations before logout', err)
    }
  }

  function setViewMode(mode: ViewMode) {
    viewMode.value = mode
  }

  function setQueryMode(mode: QueryMode) {
    if (streamInFlight.value && mode !== queryMode.value) {
      ElMessage.warning(i18n.global.t('worldInteraction.decision.streamSwitchBlocked'))
      return
    }
    queryMode.value = mode
    if (mode === 'aico' && !activeAicoThreadId.value) {
      createAicoThread()
    }
  }

  async function applyActionResponse(response: ActionResponse) {
    if (!response.success) {
      ElMessage.warning(response.result.summary)
    } else if (response.result.summary) {
      ElMessage.success(response.result.summary)
    }
    await applyStatePatch(response.state_patch)
  }

  async function applyStatePatch(patch?: StatePatch) {
    if (!patch || !interactionState.value) return
    if (patch.focusSummary) interactionState.value.decision_center.focus = patch.focusSummary
    if (patch.activeTask !== undefined) interactionState.value.decision_center.activeTask = patch.activeTask
    if (patch.newDecisionEvents) interactionState.value.decision_center.decisionEvents = patch.newDecisionEvents
    if (patch.resolvedDecisionEventIds?.length) {
      const resolved = new Set(patch.resolvedDecisionEventIds)
      interactionState.value.decision_center.decisionEvents =
        interactionState.value.decision_center.decisionEvents.filter(event => !resolved.has(event.id))
    }
    if (patch.contextSummary) interactionState.value.context_summary = patch.contextSummary
    if (patch.mapPatch) {
      try {
        await useWorldMapStore().applyMapPatch(patch.mapPatch)
      } catch (err) {
        console.warn('[worldSession] applyMapPatch failed:', err)
      }
    }
    if (patch.historyAppend) historyItems.value = [...patch.historyAppend, ...historyItems.value].slice(0, 20)
    if (patch.currentSpaceId) interactionState.value.session.currentSpaceId = patch.currentSpaceId
  }

  async function runAction<T>(fn: () => Promise<T>): Promise<T> {
    actionLoading.value = true
    try {
      return await fn()
    } finally {
      actionLoading.value = false
    }
  }

  function reset(options: { cancelServerStream?: boolean } = {}) {
    cleanupActiveStream(options)
    interactionState.value = null
    displayPolicy.value = null
    availableWorlds.value = []
    loading.value = false
    actionLoading.value = false
    error.value = null
    errorKey.value = null
    viewMode.value = 'Focus'
    queryMode.value = 'aico'
    historyItems.value = []
    clearLocalConversations()
  }

  return {
    interactionState,
    displayPolicy,
    availableWorlds,
    loading,
    actionLoading,
    error,
    errorKey,
    viewMode,
    queryMode,
    historyItems,
    commandConversation,
    aicoThreads,
    activeAicoThreadId,
    conversationMessages,
    conversationAtCap,
    streamInFlight,
    session,
    decisionCenter,
    focusMap,
    contextSummary,
    currentWorld,
    loadCurrent,
    refreshInteractionState,
    enterWorld,
    leaveWorld,
    executeDecisionAction,
    submitQuery,
    submitAicoStream,
    stopStream,
    toggleMessageExpanded,
    createAicoThread,
    setActiveAicoThread,
    clearActiveAicoThreads,
    archiveConversations,
    setViewMode,
    setQueryMode,
    applyStatePatch,
    reset,
  }
})
