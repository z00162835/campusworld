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
  /** i18n key for frontend fallback copy when no server/user content exists. */
  answerKey?: string | null
}

export interface AicoThread {
  id: string
  title?: string
  titleKey?: string
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
  mapPatch?: MapPatch
  contextSummary?: ContextSummary
  historyAppend?: Array<{ id: string; summary: string; createdAt: string }>
}
