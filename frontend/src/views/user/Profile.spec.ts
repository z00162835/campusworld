import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import Profile from './Profile.vue'

const closeAppTabMock = vi.hoisted(() => vi.fn())

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: { username: 'alice', email: 'alice@example.com' },
    token: 'token',
    fetchUser: vi.fn(),
  }),
}))

vi.mock('@/composables/useLogout', () => ({
  useLogout: () => ({
    logout: vi.fn(),
  }),
}))

vi.mock('@/composables/useAppTabs', () => ({
  useAppTabs: () => ({
    closeAppTab: closeAppTabMock,
  }),
}))

describe('Profile.vue', () => {
  beforeEach(() => {
    closeAppTabMock.mockReset()
  })

  it('closes the profile app tab when clicking the close button', async () => {
    const wrapper = mount(Profile, {
      global: {
        stubs: {
          ElButton: {
            template: '<button @click="$emit(\'click\')"><slot /></button>',
          },
          ElIcon: {
            template: '<span><slot /></span>',
          },
          Close: true,
        },
      },
    })

    await wrapper.get('.settings-close').trigger('click')

    expect(closeAppTabMock).toHaveBeenCalledWith('tab-profile')
  })
})
