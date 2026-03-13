/**
 * WebSocket Hook
 * 实时连接后端推送（带自动重连）
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '@/store/authStore'

interface WSMessage {
  type: 'status_update' | 'manual_review_required' | 'task_completed' | 'error'
  timestamp: string
  data: any
}

export function useWebSocket() {
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [messageCount, setMessageCount] = useState(0)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const { user, token } = useAuthStore()

  // 🔴 必须在 connect 函数之前声明
  const shouldReconnectRef = useRef(true)
  const isConnectingRef = useRef(false)

  const connect = useCallback(() => {
    if (!user || !token) return

    // 防止重复连接
    if (isConnectingRef.current) return
    isConnectingRef.current = true

    // 清理现有连接
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close()
    }

    // 动态获取 WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = import.meta.env.PROD ? window.location.host : 'localhost:8000'
    const wsUrl = `${protocol}//${host}/api/v1/ws/${user.id}?token=${token}`

    console.log('[WebSocket] Connecting to:', wsUrl.substring(0, 50) + '...')
    const ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log('[WebSocket] Connected successfully')
      setIsConnected(true)
      isConnectingRef.current = false
    }

    ws.onmessage = (event) => {
      try {
        const message: WSMessage = JSON.parse(event.data)
        console.log('[WebSocket] Message received:', message.type, message.data?.status)

        const messageWithId = {
          ...message,
          _id: Date.now() + Math.random()
        }

        setLastMessage(messageWithId)
        setMessageCount(prev => prev + 1)
      } catch (e) {
        console.error('[WebSocket] Parse error:', e)
      }
    }

    ws.onerror = (error) => {
      console.error('[WebSocket] Error:', error)
      isConnectingRef.current = false
    }

    ws.onclose = (event) => {
      console.log('[WebSocket] Disconnected, code:', event.code, 'reason:', event.reason)
      setIsConnected(false)
      isConnectingRef.current = false

      // 只有在 shouldReconnect 为 true 且不是主动关闭时才重连
      if (shouldReconnectRef.current && event.code !== 1000) {
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current)
        }
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log('[WebSocket] Attempting reconnect...')
          connect()
        }, 3000)
      }
    }

    wsRef.current = ws
  }, [user?.id, token]) // 🔴 只依赖 user.id 和 token

  useEffect(() => {
    if (!user?.id || !token) return

    // 重置状态
    shouldReconnectRef.current = true
    isConnectingRef.current = false

    connect()

    return () => {
      // 组件卸载时不再重连
      shouldReconnectRef.current = false
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounting') // 正常关闭
        wsRef.current = null
      }
    }
  }, [user?.id, token, connect])

  const sendMessage = (message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }

  return { lastMessage, isConnected, sendMessage, messageCount }
}
