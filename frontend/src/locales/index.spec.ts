import { describe, expect, it } from 'vitest'
import { APP_TAB_DEFINITIONS } from '@/stores/appTabs'
import { routes } from '@/router'
import en from './en'
import zh from './zh'

type LocaleTree = Record<string, unknown>

function flattenKeys(tree: LocaleTree, prefix = ''): string[] {
  return Object.entries(tree).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return flattenKeys(value as LocaleTree, path)
    }
    return [path]
  })
}

function hasKey(tree: LocaleTree, key: string): boolean {
  return key.split('.').reduce<unknown>((node, segment) => {
    if (!node || typeof node !== 'object') return undefined
    return (node as LocaleTree)[segment]
  }, tree) !== undefined
}

describe('locale message coverage', () => {
  it('keeps zh and en locale keys in sync', () => {
    expect(flattenKeys(zh).sort()).toEqual(flattenKeys(en).sort())
  })

  it('defines every route and app tab title key in both locales', () => {
    const titleKeys = [
      ...routes.map(route => route.meta?.titleKey),
      ...APP_TAB_DEFINITIONS.map(tab => tab.titleKey),
    ].filter((key): key is string => typeof key === 'string')

    for (const key of titleKeys) {
      expect(hasKey(zh, key)).toBe(true)
      expect(hasKey(en, key)).toBe(true)
    }
  })
})
