/**
 * Spaces API - Graph node queries for spaces
 *
 * Backend endpoint: /api/v1/graph/nodes
 * Uses trait filtering for performance: trait_class=SPACE, required_any_mask=516
 */

import apiClient from './index'
import { TRAIT_MASK, type SpaceListParams, type SpaceListResponse, type SpaceNode } from '@/types/space'

// Map frontend tab names to backend type_code values
const TAB_TYPE_CODE_MAP: Record<string, string> = {
  world: 'world',
  building: 'building',
  floor: 'building_floor',
  room: 'building_room',
}

export const spacesApi = {
  /**
   * Get spaces by type with optional filters
   * Uses SPACE trait for performance (trait_mask = 516)
   */
  getSpaces: (params: SpaceListParams): Promise<{ data: SpaceListResponse }> => {
    const { type_code, name_like, is_active = true, is_public, tags_any, world_id, building_id, floor_id, offset = 0, limit = 24 } = params

    // Convert tab name to backend type_code
    const resolvedTypeCode = type_code ? (TAB_TYPE_CODE_MAP[type_code] || type_code) : undefined

    const queryParams: Record<string, unknown> = {
      type_code: resolvedTypeCode,
      trait_class: 'SPACE',
      required_any_mask: TRAIT_MASK.SPACE,
      is_active,
      offset,
      limit,
    }

    if (name_like) queryParams.name_like = name_like
    if (is_public !== undefined) queryParams.is_public = is_public
    if (tags_any) queryParams.tags_any = tags_any
    if (building_id) queryParams.building_id = building_id
    if (floor_id) queryParams.floor_id = floor_id

    // Use world-scoped endpoint when world_id is specified
    if (world_id) {
      return apiClient.get<SpaceListResponse>(`/graph/worlds/${world_id}/nodes`, { params: queryParams })
    }
    return apiClient.get<SpaceListResponse>('/graph/nodes', { params: queryParams })
  },

  /**
   * Get a single space by ID
   */
  getSpace: (nodeId: number): Promise<{ data: SpaceNode }> => {
    return apiClient.get<SpaceNode>(`/graph/nodes/${nodeId}`)
  },

  /**
   * Get all nodes of a specific type (for dropdown filters)
   * Returns up to 500 items (backend max limit)
   */
  getNodesByType: (typeCode: string, options?: { world_id?: number; is_active?: boolean }): Promise<{ data: SpaceListResponse }> => {
    const params: Record<string, unknown> = {
      type_code: typeCode,
      trait_class: 'SPACE',
      required_any_mask: TRAIT_MASK.SPACE,
      is_active: options?.is_active ?? true,
      limit: 500,
    }

    // Use world-scoped endpoint when world_id is specified
    if (options?.world_id) {
      return apiClient.get<SpaceListResponse>(`/graph/worlds/${options.world_id}/nodes`, { params })
    }
    return apiClient.get<SpaceListResponse>('/graph/nodes', { params })
  },

  /**
   * Update a space node (requires graph.write permission)
   */
  updateSpace: (nodeId: number, data: Partial<SpaceNode>): Promise<{ data: SpaceNode }> => {
    return apiClient.patch<SpaceNode>(`/graph/nodes/${nodeId}`, data)
  },
}

// API error messages
export const SPACE_ERROR_MESSAGES: Record<number, string> = {
  400: 'Invalid filter parameters',
  401: 'Authentication required',
  403: 'Permission denied',
  404: 'Space not found',
  500: 'Server error loading spaces',
}
