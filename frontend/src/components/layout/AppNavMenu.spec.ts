import { beforeEach, describe, expect, it } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import AppNavMenu from './AppNavMenu.vue'
import { useTabsStore } from '@/stores/tabs'
import zh from '@/locales/zh'

const i18n = createI18n({
  legacy: false,
  locale: 'zh',
  messages: { zh },
})

const ElDropdownItemStub = defineComponent({
  name: 'ElDropdownItem',
  props: {
    command: { type: String, default: '' },
  },
  setup(props, { slots, attrs }) {
    return () =>
      h(
        'div',
        {
          class: ['el-dropdown-menu__item', attrs.class],
          'data-command': props.command,
        },
        slots.default?.(),
      )
  },
})

const ElDropdownMenuStub = defineComponent({
  name: 'ElDropdownMenu',
  setup(_, { slots }) {
    return () => h('div', { class: 'el-dropdown-menu' }, slots.default?.())
  },
})

const ElDropdownStub = defineComponent({
  name: 'ElDropdown',
  setup(_, { slots }) {
    return () =>
      h('div', { class: 'el-dropdown' }, [
        slots.default?.(),
        slots.dropdown?.(),
      ])
  },
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  setup(_, { slots }) {
    return () => h('span', { class: 'el-icon' }, slots.default?.())
  },
})

describe('AppNavMenu.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('highlights the menu item that matches the active tab route', async () => {
    const tabsStore = useTabsStore()
    tabsStore.openTabByRoute('/spaces')

    const wrapper = mount(AppNavMenu, {
      global: {
        plugins: [i18n],
        stubs: {
          ElDropdown: ElDropdownStub,
          ElDropdownMenu: ElDropdownMenuStub,
          ElDropdownItem: ElDropdownItemStub,
          ElIcon: ElIconStub,
          ArrowDown: true,
          Document: true,
          FolderOpened: true,
          User: true,
          Search: true,
          Clock: true,
        },
      },
    })

    await wrapper.vm.$nextTick()
    const activeItem = wrapper.find('.el-dropdown-menu__item.is-active')
    expect(activeItem.exists()).toBe(true)
    expect(activeItem.text()).toContain('空间')
  })
})
