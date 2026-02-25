'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

interface UseWebSocketOptions {
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  onMessage?: (data: any) => void;
  reconnect?: boolean;
  reconnectInterval?: number;
  reconnectAttempts?: number;
}

export function useWebSocket(
  path: string,
  options: UseWebSocketOptions = {}
) {
  const {
    onOpen,
    onClose,
    onError,
    onMessage,
    reconnect = true,
    reconnectInterval = 3000,
    reconnectAttempts = 5
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<any>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();

  const connect = useCallback(() => {
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      const joiner = path.includes('?') ? '&' : '?';
      const url = `${WS_BASE_URL}${path}${token ? `${joiner}token=${encodeURIComponent(token)}` : ''}`;
      const ws = new WebSocket(url);

      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        reconnectCountRef.current = 0;
        onOpen?.();
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        onClose?.();

        // 自动重连
        if (reconnect && reconnectCountRef.current < reconnectAttempts) {
          reconnectCountRef.current++;
          console.log(`Reconnecting... (${reconnectCountRef.current}/${reconnectAttempts})`);

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, reconnectInterval);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        onError?.(error);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
          onMessage?.(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      wsRef.current = ws;
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
    }
  }, [path, onOpen, onClose, onError, onMessage, reconnect, reconnectInterval, reconnectAttempts]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const send = useCallback((data: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    } else {
      console.warn('WebSocket is not connected');
    }
  }, []);

  const subscribe = useCallback((channel: string) => {
    send({
      action: 'subscribe',
      channel
    });
  }, [send]);

  const unsubscribe = useCallback((channel: string) => {
    send({
      action: 'unsubscribe',
      channel
    });
  }, [send]);

  useEffect(() => {
    connect();

    // 心跳
    const heartbeatInterval = setInterval(() => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        send({
          action: 'ping',
          timestamp: Date.now()
        });
      }
    }, 30000);

    return () => {
      clearInterval(heartbeatInterval);
      disconnect();
    };
  }, [connect, disconnect, send]);

  return {
    isConnected,
    lastMessage,
    send,
    subscribe,
    unsubscribe
  };
}
