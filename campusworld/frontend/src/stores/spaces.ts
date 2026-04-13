/**
 * Spaces Store - State management for Spaces page
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { SpaceNode, SpaceTab, ViewMode, FilterState } from '@/types/space'
import { spacesApi } from '@/api/spaces'

export const useSpacesStore = defineStore('spaces', () => {
  // Current view state
  const activeTab = ref<SpaceTab>('world')
  const viewMode = ref<ViewMode>('card')

  // Search and filter state
  const searchKeyword = ref('')
  const filters = ref<FilterState>({})

  // Data state
  const nodes = ref<Record<SpaceTab, SpaceNode[]>>({
    world: [],
    building: [],
    floor: [],
    room: [],
  })
  const totalCounts = ref<Record<SpaceTab, number>>({
    world: 0,
    building: 0,
    floor: 0,
    room: 0,
  })

  // Lookup data for filters
  const worlds = ref<SpaceNode[]>([])
  const buildings = ref<SpaceNode[]>([])
  const floors = ref<SpaceNode[]>([])

  // UI state
  const loading = ref(false)
  const currentPage = ref(1)  // 1-indexed for pagination compatibility
  const pageSize = ref(24)

  // Detail drawer state
  const selectedNode = ref<SpaceNode | null>(null)
  const detailDrawerVisible = ref(false)

  // Computed
  const currentNodes = computed(() => nodes.value[activeTab.value])
  const currentTotal = computed(() => totalCounts.value[activeTab.value])
  const hasMore = computed(() => currentNodes.value.length < currentTotal.value)

  // Actions
  async function fetchSpaces(tab?: SpaceTab, offset?: number, append = false) {
    const targetTab = tab || activeTab.value
    loading.value = true

    try {
      // For load more (append), offset is current length
      // For fresh load (not append), use provided offset or calculate from currentPage
      // currentPage is 1-indexed, so offset = (currentPage - 1) * pageSize
      const apiOffset = append
        ? nodes.value[targetTab].length
        : (offset ?? (currentPage.value - 1) * pageSize.value)

      const response = await spacesApi.getSpaces({
        type_code: targetTab,
        name_like: searchKeyword.value || undefined,
        world_id: targetTab !== 'world' ? filters.value.world_id : undefined,
        building_id: targetTab === 'floor' || targetTab === 'room' ? filters.value.building_id : undefined,
        floor_id: targetTab === 'room' ? filters.value.floor_id : undefined,
        offset: apiOffset,
        limit: pageSize.value,
      })

      const { items, page } = response.data

      // Store data for the target tab - append or replace
      if (append) {
        nodes.value[targetTab] = [...nodes.value[targetTab], ...items]
      } else {
        nodes.value[targetTab] = items
      }
      totalCounts.value[targetTab] = page.total
      // Update currentPage after fetch
      if (append) {
        // For load more, calculate the page we ended up on
        currentPage.value = Math.ceil(nodes.value[targetTab].length / pageSize.value)
      }
      // For non-append, currentPage is already correct (set by pagination or setActiveTab)
    } catch (error) {
      console.error('Failed to fetch spaces:', error)
    } finally {
      loading.value = false
    }
  }

  async function loadMore() {
    if (loading.value || !hasMore.value) return
    await fetchSpaces(undefined, undefined, true)
  }

  async function refresh() {
    currentPage.value = 1
    nodes.value[activeTab.value] = []
    await fetchSpaces()
  }

  function setActiveTab(tab: SpaceTab) {
    if (activeTab.value === tab) return
    activeTab.value = tab
    currentPage.value = 1  // Reset to first page
    // Reset filters when switching tabs (except world-level filters)
    if (tab !== 'world') {
      filters.value = {
        world_id: filters.value.world_id,
      }
    }
    // Always fetch data when switching tabs with explicit offset=0
    fetchSpaces(tab, 0, false)
  }

  function setViewMode(mode: ViewMode) {
    viewMode.value = mode
    localStorage.setItem('spaces_view_mode', mode)
  }

  function setSearchKeyword(keyword: string) {
    searchKeyword.value = keyword
  }

  function setFilters(newFilters: FilterState) {
    filters.value = { ...filters.value, ...newFilters }
  }

  function resetFilters() {
    filters.value = {}
    if (activeTab.value !== 'world') {
      filters.value.world_id = undefined
    }
  }

  function openDetail(node: SpaceNode) {
    selectedNode.value = node
    detailDrawerVisible.value = true
  }

  function closeDetail() {
    detailDrawerVisible.value = false
    selectedNode.value = null
  }

  // Filter dropdown data
  async function fetchWorlds() {
    try {
      const response = await spacesApi.getNodesByType('world')
      worlds.value = response.data.items
      return worlds.value
    } catch (error) {
      console.error('Failed to fetch worlds:', error)
      return []
    }
  }

  async function fetchBuildings(worldId?: number) {
    try {
      const response = await spacesApi.getNodesByType('building', { world_id: worldId })
      buildings.value = response.data.items
      return buildings.value
    } catch (error) {
      console.error('Failed to fetch buildings:', error)
      return []
    }
  }

  async function fetchFloors() {
    try {
      const response = await spacesApi.getNodesByType('building_floor')
      floors.value = response.data.items
      return floors.value
    } catch (error) {
      console.error('Failed to fetch floors:', error)
      return []
    }
  }

  // Initialize view mode from localStorage
  function initViewMode() {
    const saved = localStorage.getItem('spaces_view_mode') as ViewMode | null
    if (saved) viewMode.value = saved
  }

  return {
    // State
    activeTab,
    viewMode,
    searchKeyword,
    filters,
    nodes,
    totalCounts,
    worlds,
    buildings,
    floors,
    loading,
    currentPage,
    pageSize,
    selectedNode,
    detailDrawerVisible,

    // Computed
    currentNodes,
    currentTotal,
    hasMore,

    // Actions
    fetchSpaces,
    loadMore,
    refresh,
    setActiveTab,
    setViewMode,
    setSearchKeyword,
    setFilters,
    resetFilters,
    openDetail,
    closeDetail,
    fetchWorlds,
    fetchBuildings,
    fetchFloors,
    initViewMode,
  }
})
