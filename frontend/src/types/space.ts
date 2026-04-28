/**
 * Space Types - Type definitions for Spaces page
 *
 * Backend model: Node with type_code in {world, building, building_floor, room}
 * All space types share trait_class = 'SPACE', trait_mask = 516 (SPATIAL | LOAD_BEARING)
 */

// Trait mask constants (aligned with backend/app/constants/trait_mask.py)
export const TRAIT_MASK = {
  CONCEPTUAL: 1 << 0,   // 1
  FACTUAL: 1 << 1,       // 2
  SPATIAL: 1 << 2,       // 4
  PERCEPTUAL: 1 << 3,    // 8
  TEMPORAL: 1 << 4,      // 16
  CONTROLLABLE: 1 << 5,   // 32
  EVENT_BASED: 1 << 6,   // 64
  MOBILE: 1 << 7,        // 128
  AUTO: 1 << 8,          // 256
  LOAD_BEARING: 1 << 9,  // 512
  SPACE: (1 << 2) | (1 << 9), // 516 = SPATIAL | LOAD_BEARING
} as const

// Space tab types
export type SpaceTab = 'world' | 'building' | 'floor' | 'room'

// View mode types
export type ViewMode = 'card' | 'list'

// Base space node
export interface SpaceNode {
  id: number
  uuid: string
  type_code: string
  name: string
  description: string
  is_active: boolean
  is_public: boolean
  access_level: string
  trait_class: string
  trait_mask: number
  attributes: Record<string, unknown>
  tags: string[]
  created_at: string
  updated_at: string
}

// World node
export interface World extends SpaceNode {
  type_code: 'world'
  attributes: {
    world_type?: 'virtual' | 'physical' | 'mixed'
    theme?: string
    genre?: string
    difficulty?: string
    max_players?: number
    is_private: boolean
    status?: 'active' | 'offline' | 'maintenance'
    version?: string
    player_count?: number
    object_count?: number
    settings?: Record<string, unknown>
    physics?: Record<string, unknown>
    environment?: Record<string, unknown>
  }
}

// Building node
export interface Building extends SpaceNode {
  type_code: 'building'
  attributes: {
    uns?: string
    building_type?: 'academic' | 'administrative' | 'residential' | 'research' | string
    building_status?: 'active' | 'maintenance' | 'closed' | string
    building_class?: string
    building_code?: string
    building_area?: number
    building_floors?: number
    building_basement_floors?: number
    building_capacity?: number
    building_rooms?: number
    building_latitude?: number
    building_longitude?: number
    building_floors_list?: number[]
    world_id?: number
  }
}

// Floor node
export interface Floor extends SpaceNode {
  type_code: 'building_floor'
  attributes: {
    uns?: string
    floor_number: number
    floor_type?: 'normal' | 'basement' | 'mezzanine' | 'rooftop' | string
    floor_area?: number
    floor_height?: number
    floor_capacity?: number
    building_id: number
  }
}

// Room node
export interface Room extends SpaceNode {
  type_code: 'room'
  attributes: {
    uns?: string
    room_code?: string
    room_type: 'normal' | 'home' | 'special' | 'classroom' | 'office' | 'lab' | 'singularity' | string
    room_name?: string
    room_area?: number
    room_height?: number
    room_capacity?: number
    room_floor: number
    room_building?: string
    room_campus?: string
    room_temperature?: number
    room_humidity?: number
    room_lighting?: string
    room_weather?: string
    is_root?: boolean
    is_home?: boolean
    is_special?: boolean
    is_public?: boolean
    is_accessible?: boolean
    room_objects?: string[]
    room_functions?: string[]
    room_exits?: Record<string, string>
    allow_teleport?: boolean
    building_id?: number
    floor_id?: number
  }
}

// Union type for all space nodes
export type AnySpaceNode = World | Building | Floor | Room

// Filter state
export interface FilterState {
  world_id?: number
  building_id?: number
  floor_id?: number
  world_type?: string
  building_type?: string
  floor_type?: string
  room_type?: string
  status?: string[]
  is_public?: boolean
}

// Space list response
export interface SpaceListResponse {
  items: SpaceNode[]
  page: {
    total: number
    offset: number
    limit: number
  }
}

// API query params
export interface SpaceListParams {
  type_code: SpaceTab
  name_like?: string
  trait_class?: string
  required_any_mask?: number
  is_active?: boolean
  is_public?: boolean
  tags_any?: string
  world_id?: number
  building_id?: number
  floor_id?: number
  offset?: number
  limit?: number
}

// Select option for dropdowns
export interface SelectOption {
  label: string
  value: string | number
}

// Status options
export const WORLD_STATUS_OPTIONS: SelectOption[] = [
  { label: '在线 (active)', value: 'active' },
  { label: '离线 (offline)', value: 'offline' },
  { label: '维护中 (maintenance)', value: 'maintenance' },
]

export const WORLD_TYPE_OPTIONS: SelectOption[] = [
  { label: '虚拟 (virtual)', value: 'virtual' },
  { label: '物理 (physical)', value: 'physical' },
  { label: '混合 (mixed)', value: 'mixed' },
]

export const BUILDING_TYPE_OPTIONS: SelectOption[] = [
  { label: '教学楼 (academic)', value: 'academic' },
  { label: '办公楼 (administrative)', value: 'administrative' },
  { label: '宿舍 (residential)', value: 'residential' },
  { label: '研究楼 (research)', value: 'research' },
]

export const FLOOR_TYPE_OPTIONS: SelectOption[] = [
  { label: '普通 (normal)', value: 'normal' },
  { label: '地下 (basement)', value: 'basement' },
  { label: '夹层 (mezzanine)', value: 'mezzanine' },
  { label: '屋顶 (rooftop)', value: 'rooftop' },
]

export const ROOM_TYPE_OPTIONS: SelectOption[] = [
  { label: '普通 (normal)', value: 'normal' },
  { label: '主页 (home)', value: 'home' },
  { label: '特殊 (special)', value: 'special' },
  { label: '教室 (classroom)', value: 'classroom' },
  { label: '办公室 (office)', value: 'office' },
  { label: '实验室 (lab)', value: 'lab' },
  { label: '奇点屋 (singularity)', value: 'singularity' },
]

export const BUILDING_STATUS_OPTIONS: SelectOption[] = [
  { label: '正常 (active)', value: 'active' },
  { label: '维修中 (maintenance)', value: 'maintenance' },
  { label: '关闭 (closed)', value: 'closed' },
]
