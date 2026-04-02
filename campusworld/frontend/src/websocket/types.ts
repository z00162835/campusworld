/**
 * WebSocket types
 */
export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

export interface WebSocketMessage<T = unknown> {
  type: string
  payload: T
  timestamp?: number
}

export interface WebSocketOptions {
  url: string
  autoReconnect?: boolean
  reconnectInterval?: number
}
