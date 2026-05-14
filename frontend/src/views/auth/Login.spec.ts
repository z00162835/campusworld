import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Login from './Login.vue'

const pushMock = vi.hoisted(() => vi.fn())
const loginMock = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  createRouter: () => ({
    beforeEach: vi.fn(),
    push: vi.fn(),
    replace: vi.fn(),
  }),
  createWebHistory: vi.fn(),
  useRouter: () => ({
    push: pushMock,
    replace: vi.fn(),
  }),
  useRoute: () => ({
    path: '/login',
    query: {},
    params: {},
  }),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => `translated:${key}`,
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    login: loginMock,
  }),
  getAuthErrorMessage: (status: number) => {
    const messages: Record<number, string> = {
      401: 'auth.errors.invalidCredentials',
      403: 'auth.errors.accountDisabled',
      423: 'auth.errors.accountLocked',
      429: 'auth.errors.rateLimited',
    }
    return messages[status] || 'auth.errors.loginFailed'
  },
}))

const mountLogin = () => mount(Login, {
  global: {
    stubs: {
      ParticleBackground: true,
      ScanlineOverlay: true,
      BootSequence: true,
      GlitchText: true,
      SystemStatus: true,
      RouterLink: {
        props: ['to'],
        template: '<a data-test="register-link" :data-to="to"><slot /></a>',
      },
      CyberInput: {
        props: ['modelValue', 'label', 'type', 'placeholder', 'error', 'disabled'],
        emits: ['update:modelValue'],
        template: `
          <label>
            <span>{{ label }}</span>
            <input
              :type="type || 'text'"
              :value="modelValue"
              :placeholder="placeholder"
              :disabled="disabled"
              @input="$emit('update:modelValue', $event.target.value)"
            />
            <span v-if="error" class="input-error">{{ error }}</span>
          </label>
        `,
      },
      CyberButton: {
        props: ['label', 'loading', 'disabled'],
        emits: ['click'],
        template: '<button type="submit" :disabled="disabled" @click="$emit(\'click\')">{{ label }}</button>',
      },
    },
  },
})

describe('Login.vue', () => {
  beforeEach(() => {
    loginMock.mockReset()
    pushMock.mockReset()
    sessionStorage.setItem('boot_sequence_shown', 'true')
  })

  it('uses SPA navigation for the register link', () => {
    const wrapper = mountLogin()
    const link = wrapper.get('[data-test="register-link"]')

    expect(link.attributes('data-to')).toBe('/register')
    expect(link.attributes('href')).toBeUndefined()
  })

  it('shows mapped safe auth error messages', async () => {
    loginMock.mockResolvedValue({ success: false, status: 423 })
    const wrapper = mountLogin()
    const inputs = wrapper.findAll('input')

    await inputs[0].setValue('alice')
    await inputs[1].setValue('secret1')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('translated:auth.errors.accountLocked')
  })

  it('redirects to works after successful login without unsafe redirect input', async () => {
    loginMock.mockResolvedValue({ success: true })
    const wrapper = mountLogin()
    const inputs = wrapper.findAll('input')

    await inputs[0].setValue('alice')
    await inputs[1].setValue('secret1')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(pushMock).toHaveBeenCalledWith('/works')
  })
})
