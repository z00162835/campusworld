import { describe, it, expect } from 'vitest'
import {
  DEFAULT_TASK_SPLIT_RATIO,
  nextFoldMode,
  resolveDragRatio,
  SNAP_TO_COLLAPSED_RATIO,
  SNAP_TO_MAXIMIZED_RATIO,
} from '../useDecisionFoldLayout'

describe('useDecisionFoldLayout helpers', () => {
  it('cycles collapsed → split → maximized → collapsed', () => {
    expect(nextFoldMode('collapsed')).toBe('split')
    expect(nextFoldMode('split')).toBe('maximized')
    expect(nextFoldMode('maximized')).toBe('collapsed')
  })

  it('snaps drag ratio to maximized or collapsed thresholds', () => {
    expect(resolveDragRatio(SNAP_TO_MAXIMIZED_RATIO)).toEqual({
      mode: 'maximized',
      ratio: DEFAULT_TASK_SPLIT_RATIO,
    })
    expect(resolveDragRatio(SNAP_TO_COLLAPSED_RATIO)).toEqual({
      mode: 'collapsed',
      ratio: DEFAULT_TASK_SPLIT_RATIO,
    })
    expect(resolveDragRatio(0.5)).toEqual({ mode: 'split', ratio: 0.5 })
  })
})
