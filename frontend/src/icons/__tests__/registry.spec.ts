import { describe, expect, it } from 'vitest'
import { APP_TAB_DEFINITIONS } from '@/stores/appTabs'
import { getIconComponent, ICON_REGISTRY, isIconName } from '../index'

describe('icon registry', () => {
  it('registers every app tab icon key', () => {
    for (const tab of APP_TAB_DEFINITIONS) {
      expect(isIconName(tab.iconKey)).toBe(true)
      expect(getIconComponent(tab.iconKey)).toBeTruthy()
    }
  })

  it('keeps registry keys aligned with IconName type', () => {
    expect(Object.keys(ICON_REGISTRY).sort()).toEqual([
      'agents',
      'chevronDown',
      'chevronLeft',
      'chevronRight',
      'chevronUp',
      'close',
      'commandMode',
      'context',
      'conversation',
      'decision',
      'decisionTasks',
      'discovery',
      'history',
      'loading',
      'map',
      'profile',
      'send',
      'spaces',
      'stop',
      'works',
    ])
  })
})
