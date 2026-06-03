import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import QueryResultCard from '../QueryResultCard.vue'
import type { ConversationMessage } from '@/types/world'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

vi.mock('@/stores/worldSession', () => ({
  useWorldSessionStore: () => ({
    toggleMessageExpanded: vi.fn(),
  }),
}))

describe('QueryResultCard', () => {
  it('shows stream status and cursor inside the assistant card while streaming', () => {
    setActivePinia(createPinia())
    const message: ConversationMessage = {
      id: 'a1',
      role: 'assistant',
      mode: 'aico',
      answer: '',
      streaming: true,
      streamStatusKey: 'generating',
    }
    const wrapper = mount(QueryResultCard, {
      props: { message },
    })
    expect(wrapper.find('.stream-status').exists()).toBe(true)
    expect(wrapper.find('.stream-status-text').text()).toContain('streamStatus.generating')
    expect(wrapper.find('.stream-typing-dots').exists()).toBe(true)
    expect(wrapper.find('.answer-output').exists()).toBe(false)
  })

  it('renders streamed answer text in the same card', () => {
    setActivePinia(createPinia())
    const message: ConversationMessage = {
      id: 'a2',
      role: 'assistant',
      mode: 'aico',
      answer: 'Hello campus',
      streaming: true,
      streamStatusKey: 'generating',
    }
    const wrapper = mount(QueryResultCard, {
      props: { message },
    })
    expect(wrapper.find('.markdown-content').text()).toContain('Hello campus')
    expect(wrapper.find('.stream-caret').exists()).toBe(true)
  })

  it('shows localized role labels instead of raw role and mode', () => {
    setActivePinia(createPinia())
    const user = mount(QueryResultCard, {
      props: {
        message: {
          id: 'u1',
          role: 'user',
          mode: 'aico',
          query: 'hello',
          answer: 'hello',
        },
      },
    })
    expect(user.find('.role').text()).toBe('worldInteraction.decision.messageRole.you')
    expect(user.find('.mode').exists()).toBe(false)

    const assistant = mount(QueryResultCard, {
      props: {
        message: {
          id: 'a1',
          role: 'assistant',
          mode: 'aico',
          answer: 'ok',
        },
      },
    })
    expect(assistant.find('.role').text()).toBe('worldInteraction.decision.messageRole.aico')
  })

  it('renders command mode answers as plain text', () => {
    setActivePinia(createPinia())
    const message: ConversationMessage = {
      id: 'c1',
      role: 'assistant',
      mode: 'command',
      answer: '**not bold**',
    }
    const wrapper = mount(QueryResultCard, {
      props: { message },
    })
    expect(wrapper.find('.markdown-content').exists()).toBe(false)
    expect(wrapper.find('.command-output').text()).toBe('**not bold**')
  })
})
