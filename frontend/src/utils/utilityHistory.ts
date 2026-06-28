import type { WorldHistoryGroup } from '@/api/worldHistory'
import type { AicoThread, ConversationMessage } from '@/types/world'

export interface UtilityHistoryItem {
  id: string
  summary: string
  createdAt: string
}

export interface UtilityConversationEntry {
  id: string
  title: string
  messageCount: number
  preview: string
  updatedAt: string
}

export interface UtilityCommandEntry {
  id: string
  label: string
  detail: string
  createdAt?: string
  sequence?: number
}

function truncate(text: string, max = 56): string {
  const clean = text.trim()
  if (clean.length <= max) return clean
  return `${clean.slice(0, max)}…`
}

export function resolveThreadTitle(
  thread: AicoThread,
  fallbackTitle: string,
): string {
  if (thread.title?.trim()) return thread.title.trim()
  const firstUser = thread.messages.find(message => message.role === 'user')
  const query = firstUser?.query || firstUser?.answer || ''
  if (query.trim()) return truncate(query, 32)
  return fallbackTitle
}

export function conversationPreview(messages: ConversationMessage[]): string {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    const text =
      message.role === 'user'
        ? message.query || message.answer
        : message.answer || message.query
    if (text?.trim()) return truncate(text)
  }
  return ''
}

export function buildConversationEntries(
  threads: AicoThread[],
  archivedGroups: WorldHistoryGroup[],
  fallbackTitle: string,
): UtilityConversationEntry[] {
  const liveEntries = threads
    .filter(thread => thread.messages.length > 0)
    .map(thread => ({
      id: thread.id,
      title: resolveThreadTitle(thread, fallbackTitle),
      messageCount: thread.messages.length,
      preview: conversationPreview(thread.messages),
      updatedAt: thread.updatedAt,
    }))

  const archivedEntries: UtilityConversationEntry[] = []
  for (const group of archivedGroups) {
    if (group.id !== 'aico_conversations') continue
    for (const item of group.items) {
      archivedEntries.push({
        id: item.id,
        title: item.title || item.summary || '',
        messageCount: item.messageCount ?? 0,
        preview: item.preview || group.title,
        updatedAt: item.createdAt,
      })
    }
  }

  return [...liveEntries, ...archivedEntries].sort(
    (left, right) => Date.parse(right.updatedAt) - Date.parse(left.updatedAt),
  )
}

export function aggregateCommandMessages(
  messages: ConversationMessage[],
): UtilityCommandEntry[] {
  const entries: UtilityCommandEntry[] = []

  for (let index = 0; index < messages.length; index += 1) {
    const message = messages[index]
    if (message.mode !== 'command') continue

    if (message.role === 'user') {
      const assistant =
        messages[index + 1]?.role === 'assistant' && messages[index + 1]?.mode === 'command'
          ? messages[index + 1]
          : null
      const label = message.query || message.answer || ''
      const detail =
        assistant?.answer ||
        assistant?.commandResult?.message ||
        message.answer ||
        label
      if (!label.trim() && !detail.trim()) continue
      entries.push({
        id: message.id,
        label: truncate(label, 48),
        detail: truncate(detail),
      })
      if (assistant) index += 1
      continue
    }

    if (message.role === 'assistant') {
      const label = message.query || truncate(message.answer, 48)
      entries.push({
        id: message.id,
        label,
        detail: truncate(message.answer),
      })
    }
  }

  return entries.reverse()
}

export function buildCommandEntries(
  commandMessages: ConversationMessage[],
  actionHistory: UtilityHistoryItem[],
  archivedGroups: WorldHistoryGroup[],
): UtilityCommandEntry[] {
  const sessionEntries = aggregateCommandMessages(commandMessages)
  const actionEntries = actionHistory.map(item => ({
    id: item.id,
    label: truncate(item.summary, 48),
    detail: truncate(item.summary),
    createdAt: item.createdAt,
    sequence: undefined as number | undefined,
  }))

  const archivedEntries: UtilityCommandEntry[] = []
  for (const group of archivedGroups) {
    if (group.id !== 'command_conversations') continue
    for (const item of group.items) {
      archivedEntries.push({
        id: item.id,
        label: truncate(item.title || item.summary || '', 48),
        detail: truncate(item.detail || item.summary || group.title),
        createdAt: item.createdAt,
        sequence: item.sequence,
      })
    }
  }

  const merged = [...sessionEntries, ...actionEntries, ...archivedEntries]
  const seen = new Set<string>()
  return merged.filter(entry => {
    if (seen.has(entry.id)) return false
    seen.add(entry.id)
    return true
  }).sort((left, right) => {
    const leftTime = left.createdAt ? Date.parse(left.createdAt) : Number.MAX_SAFE_INTEGER
    const rightTime = right.createdAt ? Date.parse(right.createdAt) : Number.MAX_SAFE_INTEGER
    if (rightTime !== leftTime) return rightTime - leftTime
    return (right.sequence ?? 0) - (left.sequence ?? 0)
  })
}
