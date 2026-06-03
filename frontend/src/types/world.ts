export const CAMPUS_HUB_WORLD_ID = '__campus_hub__' as const

export type ViewMode = 'Focus' | 'Map'
export type QueryMode = 'command' | 'aico'

export interface ConversationMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  mode: QueryMode
  query?: string
  answer: string
  results?: Array<{
    entity_id: string
    entity_type: string
    title: string
    summary: string
    actions?: DecisionOption[]
  }>
  commandResult?: {
    success: boolean
    message: string
    data?: Record<string, unknown> | null
    error?: string | null
  }
  expanded?: boolean
  streaming?: boolean
  cancelled?: boolean
  /** Activity label while ``streaming`` (shown inside the assistant card). */
  streamStatusKey?: string | null
}

export interface AicoThread {
  id: string
  title: string
  messages: ConversationMessage[]
  updatedAt: string
}

export interface DecisionOption {
  id: string
  label: string
  style: 'primary' | 'secondary' | 'safe' | 'danger' | 'quiet'
  actionType: string
  command?: string | null
  targetEntityId?: string | null
  requiresConfirmation: boolean
}

export interface EntityReference {
  id: string
  type: 'space' | 'agent' | 'object' | 'task' | 'event' | 'command'
  label: string
}

export interface FocusSummary {
  title: string
  summary: string
  currentSpaceId: string
  currentTaskId?: string | null
  severity: 'normal' | 'info' | 'warning' | 'critical'
  primaryAction?: DecisionOption | null
}

export interface DecisionEvent {
  id: string
  title: string
  summary: string
  type: string
  priority: 'urgent' | 'important' | 'normal' | 'low'
  status: 'new' | 'seen' | 'resolved' | 'dismissed' | 'snoozed'
  source: string
  impact: string
  recommendation: string
  options: DecisionOption[]
  explanation?: string
  relatedEntities: EntityReference[]
  createdAt: string
}

export interface TaskStep {
  id: string
  title: string
  shortInstruction: string
  status: 'locked' | 'active' | 'completed'
  expectedAction?: string | null
}

export interface TaskCard {
  id: string
  title: string
  summary: string
  status: 'not_started' | 'active' | 'blocked' | 'completed'
  progress: number
  currentStep: TaskStep
  nextBestAction: DecisionOption
  alternativeActions: DecisionOption[]
  blockers?: Array<{ id: string; reason: string; resolutionAction?: DecisionOption }>
}

export interface SemanticMapNode {
  id: string
  name: string
  type: 'gate' | 'bridge' | 'plaza' | 'building' | 'room' | 'service' | 'hidden'
  x: number
  y: number
  status: 'unknown' | 'visible' | 'discovered' | 'current' | 'active' | 'locked' | 'warning'
  semanticTags: string[]
  activeAgentIds: string[]
  activeEventIds: string[]
  objectIds: string[]
}

export interface SemanticMapEdge {
  id: string
  from: string
  to: string
  label?: string
  direction?: string
  status: 'available' | 'locked' | 'recommended' | 'visited'
  targetLabel?: string
}

export interface AgentMapPresence {
  agentId: string
  name: string
  role: string
  currentSpaceId: string
  status: 'idle' | 'waiting' | 'talking' | 'moving' | 'working' | 'offline'
  currentIntent?: string
  currentTask?: string
  lastSeenAt: string
  visibility: 'visible' | 'discovered' | 'hidden'
}

export interface FocusMap {
  mode: 'focus' | 'route' | 'agent' | 'event'
  nodes: SemanticMapNode[]
  edges: SemanticMapEdge[]
  agentPresences: AgentMapPresence[]
  highlightedPath: string[]
  currentSpaceId: string | null
  selectedEntityId: string | null
  loading: boolean
}

export interface QueryHint {
  label: string
  query: string
  scope?: 'task' | 'map' | 'agent' | 'history' | 'world'
}

export interface LastHandledTask {
  id: string
  title: string
  status: string
  handledAt: string | null
}

export interface ContextSummary {
  currentSpace: {
    id: string
    name: string
    oneLineSummary: string
  }
  nearbyAgents: {
    total: number
    highlighted: Array<{ id: string; name: string; role: string; status: AgentMapPresence['status']; locationName: string }>
  }
  activeTask?: {
    id: string
    title: string
    currentStep: string
    progress: number
  }
  lastHandledTask?: LastHandledTask
  pendingDecisionCount: number
  suggestedQueries: QueryHint[]
}

export interface DecisionCenterStatePayload {
  focus: FocusSummary | null
  decisionEvents: DecisionEvent[]
  activeTask: TaskCard | null
  nextBestAction: DecisionOption | null
  quickQueries: QueryHint[]
  loading: boolean
  error: string | null
}

export interface WorldSession {
  id: string
  currentWorldId: string | null
  currentSpaceId: string | null
  currentSpaceKey?: string | null
  updatedAt: string
}

export interface WorldSummary {
  world_id: string
  name: string
  status: string
  is_current: boolean
  is_recommended: boolean
  entry_hint: string
}

export interface WorldInteractionState {
  session: WorldSession
  decision_center: DecisionCenterStatePayload
  focus_map: FocusMap
  context_summary: ContextSummary
  quick_queries: QueryHint[]
}

export interface DisplayPolicy {
  maxDecisionEventsVisible: number
  maxActionsPerCard: number
  maxMapNodesVisible: number
  maxAgentsHighlighted: number
  contextDefaultCollapsed: boolean
  mapDefaultCollapsed: boolean
  historyDefaultCollapsed: boolean
}

export interface StatePatch {
  currentSpaceId?: string
  resolvedDecisionEventIds?: string[]
  newDecisionEvents?: DecisionEvent[]
  activeTask?: TaskCard | null
  focusSummary?: FocusSummary
  mapPatch?: {
    mode?: FocusMap['mode']
    visibleNodeIds?: string[]
    highlightedNodeIds?: string[]
    highlightedAgentIds?: string[]
    highlightedPath?: string[]
  }
  contextSummary?: ContextSummary
  historyAppend?: Array<{ id: string; summary: string; createdAt: string }>
}
