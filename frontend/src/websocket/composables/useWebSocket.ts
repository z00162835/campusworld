/**
 * WebSocket composable
 */
import { ref, onUnmounted } from 'vue'
import wsManager from '../index'
import type { WebSocketStatus, WebSocketMessage } from '../types'

export function useWebSocket() {
  const status = ref<WebSocketStatus>('disconnected')
  const lastMessage = ref<WebSocketMessage | null>(null)

  const connect = (url: string) => {
    wsManager.connect(url)
    status.value = wsManager.getStatus()
  }

  const disconnect = () => {
    wsManager.disconnect()
    status.value = 'disconnected'
  }

  const send = (type: string, payload: unknown) => {
    wsManager.send(type, payload)
  }

  const onMessage = (type: string, handler: (msg: WebSocketMessage) => void) => {
    wsManager.on(type, handler)
  }

  onUnmounted(() => {
    // Cleanup if needed
  })

  return {
    status,
    lastMessage,
    connect,
    disconnect,
    send,
    onMessage,
  }
}
