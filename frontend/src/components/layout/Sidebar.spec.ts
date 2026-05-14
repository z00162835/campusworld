import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Sidebar from './Sidebar.vue'
import { useTabsStore } from '@/stores/tabs'

describe('Sidebar.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('highlights the menu item that matches the active tab route', () => {
    const tabsStore = useTabsStore()
    tabsStore.openTabByRoute('/spaces')

    const wrapper = mount(Sidebar, {
      global: {
        stubs: {
          Document: true,
          FolderOpened: true,
          User: true,
          Search: true,
          Clock: true,
        },
      },
    })

    const activeItem = wrapper.get('.sidebar-item.active')
    expect(activeItem.text()).toContain('Spaces')
  })
})
