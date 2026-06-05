import { describe, it, expect, vi, afterEach } from 'vitest'
import { scrollElementToBottom } from '../scrollToBottom'

describe('scrollElementToBottom', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('sets scrollTop to scrollHeight after layout frames', async () => {
    const element = document.createElement('div')
    Object.defineProperty(element, 'scrollHeight', { value: 480, configurable: true })
    let scrollTop = 0
    Object.defineProperty(element, 'scrollTop', {
      get: () => scrollTop,
      set: (value: number) => {
        scrollTop = value
      },
      configurable: true,
    })

    const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockImplementation(cb => {
      cb(0)
      return 1
    })

    await scrollElementToBottom(element)

    expect(scrollTop).toBe(480)
    expect(rafSpy).toHaveBeenCalled()
  })
})
