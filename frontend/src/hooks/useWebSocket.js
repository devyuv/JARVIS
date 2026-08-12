import { useEffect, useRef, useState } from "react";

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8765";
const RECONNECT_DELAY_MS = 2000;

/**
 * Connects to the backend's broadcast WebSocket and dispatches incoming
 * events by type via `handlers`, e.g.:
 *
 *   useWebSocket({
 *     gesture: (data) => ...,
 *     status: (data) => ...,
 *     transcript_final: (data) => ...,
 *     hardware: (data) => ...,
 *   })
 *
 * Reconnects automatically with a fixed backoff if the backend isn't up
 * yet or drops — the HUD should never hard-fail just because Python
 * hasn't started.
 */
export function useWebSocket(handlers) {
  const [connected, setConnected] = useState(false);
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    let socket;
    let reconnectTimer;
    let cancelled = false;

    const connect = () => {
      socket = new WebSocket(WS_URL);

      socket.onopen = () => setConnected(true);

      socket.onclose = () => {
        setConnected(false);
        if (!cancelled) {
          reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };

      socket.onerror = () => socket.close();

      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          const handler = handlersRef.current?.[msg.type];
          if (handler) handler(msg.data);
        } catch (err) {
          console.warn("Bad WS message", err);
        }
      };
    };

    connect();

    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);

  return { connected };
}
