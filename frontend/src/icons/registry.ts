import type { Component } from 'vue'
import {
  ArrowDown,
  ArrowUp,
  ChatRound,
  Clock,
  Close,
  Compass,
  DArrowLeft,
  DArrowRight,
  DataBoard,
  FolderOpened,
  Loading,
  MapLocation,
  Monitor,
  Platform,
  Promotion,
  Reading,
  Tickets,
  User,
  UserFilled,
  VideoPause,
} from '@element-plus/icons-vue'
import type { IconName } from './types'

export const ICON_REGISTRY: Record<IconName, Component> = {
  works: Platform,
  spaces: FolderOpened,
  agents: UserFilled,
  discovery: Compass,
  history: Clock,
  profile: User,
  map: MapLocation,
  context: Reading,
  decision: DataBoard,
  decisionTasks: Tickets,
  conversation: ChatRound,
  commandMode: Monitor,
  send: Promotion,
  stop: VideoPause,
  loading: Loading,
  chevronUp: ArrowUp,
  chevronDown: ArrowDown,
  chevronLeft: DArrowLeft,
  chevronRight: DArrowRight,
  close: Close,
}

export function getIconComponent(name: IconName): Component {
  return ICON_REGISTRY[name]
}

export function isIconName(value: string): value is IconName {
  return value in ICON_REGISTRY
}
