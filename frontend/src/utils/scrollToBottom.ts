import { nextTick } from 'vue'

/** Scroll a scrollable container to its bottom after layout and paint settle. */
export async function scrollElementToBottom(element: HTMLElement | null | undefined): Promise<void> {
  if (!element) return
  await nextTick()

  const apply = () => {
    element.scrollTop = element.scrollHeight
  }

  apply()
  await new Promise<void>(resolve => {
    requestAnimationFrame(() => {
      apply()
      requestAnimationFrame(() => {
        apply()
        resolve()
      })
    })
  })
}
