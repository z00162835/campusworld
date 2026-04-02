/**
 * WebSocket Manager
 */
import type { WebSocketStatus, WebSocketMessage } from './types'

class WebSocketManager {
  private ws: WebSocket | null = null
  private status: WebSocketStatus = 'disconnected'
  private reconnectTimer: number | null = null
  private messageHandlers: Map<string, (msg: WebSocketMessage) => void> = new Map()
  private options: { url: string; autoReconnect: boolean; reconnectInterval: number } = {
    url: '',
    autoReconnect: true,
    reconnectInterval: 3000,
  }

  connect(url: string) {
    if (this.ws?.readyState === WebSocket.OPEN) return
    if (this.ws?.readyState === WebSocket.CONNECTING) return

    this.options.url = url
    this.status = 'connecting'
    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      this.status = 'connected'
    }

    this.ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data)
        const handler = this.messageHandlers.get(message.type)
        handler?.(message)
      } catch {
        // Ignore parse errors
      }
    }

    this.ws.onclose = () => {
      this.status = 'disconnected'
      if (this.options.autoReconnect) {
        this.scheduleReconnect()
      }
    }

    this.ws.onerror = () => {
      this.status = 'error'
    }
  }

  on(type: string, handler: (msg: WebSocketMessage) => void) {
    this.messageHandlers.set(type, handler)
  }

  send(type: string, payload: unknown) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, payload, timestamp: Date.now() }))
    }
  }

  disconnect() {
    this.options.autoReconnect = false
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.ws?.close()
    this.ws = null
    this.status = 'disconnected'
  }

  getStatus(): WebSocketStatus {
    return this.status
  }

  private scheduleReconnect() {
    this.reconnectTimer = window.setTimeout(() => {
      if (this.options.url) {
        this.connect(this.options.url)
      }
    }, this.options.reconnectInterval)
  }
}

export const wsManager = new WebSocketManager()
export default wsManager
