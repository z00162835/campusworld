export const CAMPUS_HUB_WORLD_ID = '__campus_hub__' as const

export type ViewMode = 'Focus' | 'Map'
export type QueryMode = 'command' | 'aico'

export type QuerySubmission =
  | { accepted: false }
  | { accepted: true; completion: Promise<void> }

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
  /** i18n key for frontend fallback copy when no server/user content exists. */
  answerKey?: string | null
}

export interface AicoThread {
  id: string
  title?: string
  titleKey?: string
  messages: ConversationMessage[]
  updatedAt: string
  questContext?: QuestConversationContext
}

export interface QuestConversationContext {
  quest_id: string
  objective_id?: string
  agent_node_id?: string
  projection_revision: string
}

export interface DecisionOption {
  id: string
  label: string
  style: 'primary' | 'secondary' | 'safe' | 'danger' | 'quiet'
  actionType: string
  command?: string | null
  targetEntityId?: string | null
  requiresConfirmation: boolean
  labelKey?: string
  labelParams?: Record<string, string | number>
  consequenceKind?: 'confirmed' | 'predicted' | 'proposed'
  consequenceSummary?: string
  consequenceSummaryKey?: string
  consequenceProvenanceRefs?: string[]
  consequenceConfidence?: number
  riskLevel?: 'low' | 'normal' | 'high' | 'critical'
  gateStatus?: 'clear' | 'approval_required' | 'blocked' | 'evidence_required'
  requiredEvidenceRefs?: string[]
  reversible?: boolean
  affectedEntityRefs?: string[]
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
  questId?: string | null
  questTitle?: string | null
  questContext?: {
    state: string
    riskLevel: 'low' | 'normal' | 'high' | 'critical' | string
    situation?: {
      id: string
      title: string
      assertion: string
      subjectRef?: string | null
      relatedEntityRefs?: string[]
      scopedAtRef?: string | null
      triggerKind: 'hard_rule' | 'weak_experience' | 'manual' | 'mixed' | string
      confidence?: number | null
      severity: 'low' | 'medium' | 'high' | 'critical' | string
    } | null
    goal?: {
      id: string
      title: string
      desiredState: string
    } | null
    governanceRefs: string[]
    processRefs: string[]
    qualityRefs: string[]
    caseRefs: string[]
    progress?: number
    companion?: { id: string; name: string; role: string; isPrimary: boolean } | null
    companionFallback?: 'aico' | null
  } | null
  progress: number | null
  currentStep: TaskStep
  nextBestAction: DecisionOption
  alternativeActions: DecisionOption[]
  blockers?: Array<{ id: string; reason: string; resolutionAction?: DecisionOption }>
}

export type MapViewLayer = 'room' | 'floor' | 'building' | 'campus' | 'world'

export interface MapBreadcrumb {
  layer: string
  id: string
  name: string
  role?: 'hub' | 'world' | 'campus_spot' | 'building' | 'floor' | 'room' | string
}

export interface NeighborMapLink {
  direction: string
  targetId: string
  targetName: string
  summary: string
}

export interface SpaceSummaryData {
  space_node: {
    id: number
    type_code: string
    name: string
    parent_id: number | null
  }
  section1_appearance: { message_fragment: string; lines: string[] }
  section2_occupants: Array<{ id: number; name: string; type_code: string }>
  section3_devices: Array<{ id: number; name: string; status: string }>
  section4_next_or_adjacent: Array<{
    id: number
    name: string
    direction?: string | null
    description?: string
  }>
  section4_mode: string
  section4_fallback: boolean
}

export interface EntityInspectData {
  entity: {
    id: string
    name: string
    type_code: string
    map_node_type: string
  }
  entity_kind: 'person' | 'object' | 'device' | 'agent'
  appearance: { lines: string[] }
  status?: Array<{ label: string; value: string }> | null
  attributes_preview?: Array<{ key: string; value: string }> | null
  location?: { id: string; name: string } | null
  actions: DecisionOption[]
  source: 'look' | 'space'
}

export type MapInspectSelection =
  | { entityId: string; entityKind: 'space'; inspect: SpaceSummaryData }
  | { entityId: string; entityKind: 'person' | 'object' | 'device' | 'agent'; inspect: EntityInspectData }


export interface SemanticMapNode {
  id: string
  name: string
  type:
    | 'gate'
    | 'bridge'
    | 'plaza'
    | 'building'
    | 'room'
    | 'floor'
    | 'outdoor'
    | 'world'
    | 'hub'
    | 'object'
    | 'device'
    | 'agent'
    | 'service'
    | 'hidden'
    | 'cluster'
  buildingId?: string
  floorId?: string
  floorNumber?: number
  drillAnchorId?: string
  logicalZone?: 'hub' | 'occupant' | 'device' | 'item' | 'exit'
  crossBuilding?: boolean
  x: number
  y: number
  status: 'unknown' | 'visible' | 'discovered' | 'current' | 'active' | 'locked' | 'warning'
  semanticTags: string[]
  activeAgentIds: string[]
  activeEventIds: string[]
  objectIds: string[]
  groupMembers?: RoomContentGroupMember[]
  overflowCount?: number
  mapGridCol?: number
  mapGridRow?: number
  mapGridSpanW?: number
  mapGridSpanH?: number
  roomType?: string
}

export interface SemanticMapEdge {
  id: string
  from: string
  to: string
  label?: string
  direction?: string
  status: 'available' | 'locked' | 'recommended' | 'visited' | 'cross-building'
  targetLabel?: string
  crossBuilding?: boolean
  campusEdgeKind?: 'spine' | 'inter-building' | 'connector'
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

export interface FloorRoomListItem {
  id: string
  name: string
  status: SemanticMapNode['status']
}

export interface FloorStackItem {
  id: string
  name: string
  floorNumber?: number
  status: SemanticMapNode['status']
}

export interface FloorGridBounds {
  minCol: number
  minRow: number
  maxCol: number
  maxRow: number
  cellPx: number
  originX: number
  originY: number
}

export interface RoomOccupantListItem {
  id: string
  name: string
  type: SemanticMapNode['type']
  status: SemanticMapNode['status']
}

export interface RoomContentGroupMember {
  id: string
  name: string
  type: SemanticMapNode['type']
  status: SemanticMapNode['status']
}

export interface MapPatch {
  mode?: FocusMap['mode']
  viewLayer?: MapViewLayer
  anchorId?: string
  highlightedNodeIds?: string[]
  highlightedPath?: string[]
  visibleNodeIds?: string[]
  agentPresences?: AgentMapPresence[]
  focus_map?: FocusMap
}

export interface FocusMap {
  mode: 'focus' | 'route' | 'agent' | 'event'
  viewLayer?: MapViewLayer
  orientation?: 'north-up'
  layout?: 'compass' | 'grid' | 'campus-grid' | 'hierarchy' | 'list' | 'logical'
  breadcrumb?: MapBreadcrumb[]
  neighborLinks?: NeighborMapLink[]
  floorPlanReady?: boolean
  floorRoomList?: FloorRoomListItem[]
  floorStack?: FloorStackItem[]
  floorGridBounds?: FloorGridBounds | null
  roomOccupants?: RoomOccupantListItem[]
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
    progress?: number | null
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

export type QuestInteractionCapability =
  | 'multi_quest_tracking'
  | 'durable_focus'
  | 'observation_clues'
  | 'quest_graph'
  | 'situation_attention'
  | 'structured_conversation'
  | 'world_feedback'

export interface TrackedQuestSummary {
  id: string
  title: string
  state: string
  riskLevel: string
  tracking: 'explicit'
  focusedObjectiveId?: string | null
  recommendedObjectiveId?: string | null
  situation?: {
    id: string
    assertion: string
    triggerKind?: string
    confidence?: number | null
    severity?: string
    primarySubjectRef?: string | null
    relatedEntityRefs?: string[]
    scopedAtRef?: string | null
  } | null
  goal?: { id: string; desiredState: string } | null
  objectives: Array<{ id: string; title: string; state: string }>
  clues?: Array<{
    id: string
    title: string
    assertion: string
    verificationStatus: string
    sourceRef?: string | null
    observedAt?: string | null
    pinned: boolean
  }>
  companion?: { id: string; name: string; role: string; isPrimary: boolean } | null
  companionFallback?: 'aico' | null
  progress?: {
    total_objectives: number
    terminal_objectives: number
    completed_objectives: number
    percent: number
    success_percent: number
  }
}

export interface QuestJournalNode {
  id: string
  type: string
  label: string
  verificationStatus?: string
}

export interface QuestJournalEdge {
  id: string
  type: string
  sourceId: string
  targetId: string
}

export interface QuestInteractionStatePayload {
  contractVersion: 'quest-interaction.v1'
  capabilities: QuestInteractionCapability[]
  projectionRevision: string
  lastEventId?: string | null
  trackedQuests: TrackedQuestSummary[]
  foregroundQuestId?: string | null
  questJournal?: {
    nodes: QuestJournalNode[]
    edges: QuestJournalEdge[]
    unresolvedRefs: Array<{
      ref: string
      expectedType?: string
      reason: 'not_materialized' | 'not_visible' | 'not_found'
    }>
  }
  worldPulse?: WorldPulseItem[]
  worldFeedback?: WorldFeedbackItem[]
}

export interface WorldPulseItem {
  id: string
  situationId: string
  severity: string
  assertion: string
  attention: 'new' | 'seen' | 'snoozed' | 'ui_dismissed'
  snoozedUntil?: string | null
}

export interface WorldFeedbackItem {
  id: string
  questId: string
  objectiveId?: string
  actorKind: 'human' | 'agent' | 'system'
  actorId?: string | null
  status: 'succeeded' | 'failed' | 'blocked' | 'escalated'
  summary: string
  objectiveState?: string
  correlationId: string
  occurredAt: string
}

export type QuestInteractionActionPayload =
  | { action: 'track' | 'untrack'; questId: string; correlationId?: string }
  | { action: 'focus_objective'; questId: string; objectiveId: string; correlationId?: string }
  | { action: 'pin_clue' | 'unpin_clue'; questId: string; clueNodeId: string; correlationId?: string }
  | {
      action: 'set_collaborator' | 'remove_collaborator'
      questId: string
      agentNodeId: string
      role?: string
      status?: string
      isPrimaryCompanion?: boolean
      capabilityScope?: string[]
      correlationId?: string
    }
  | {
      action: 'situation_attention'
      situationId: string
      attention: 'seen' | 'snoozed' | 'ui_dismissed' | 'reset'
      snoozedUntil?: string
      correlationId?: string
    }

export interface WorldInteractionState {
  session: WorldSession
  decision_center: DecisionCenterStatePayload
  focus_map: FocusMap
  context_summary: ContextSummary
  quest_interaction?: QuestInteractionStatePayload
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
  mapPatch?: MapPatch
  contextSummary?: ContextSummary
  questInteraction?: QuestInteractionStatePayload
  historyAppend?: Array<{ id: string; summary: string; createdAt: string }>
}
