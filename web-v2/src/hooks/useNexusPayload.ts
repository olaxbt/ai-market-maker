import { useEffect, useState } from "react";
import { fetchNexusPayload, type NexusPayload } from "../lib/fetchNexusPayload";

function resolveFlowWsUrl(): string {
  const explicit = import.meta.env.VITE_FLOW_WS_URL?.trim();
  if (explicit) {
    if (explicit.includes("/ws/")) return explicit;
    return `${explicit.replace(/\/$/, "")}/ws/runs/latest`;
  }

  const apiBase = import.meta.env.VITE_FLOW_API_BASE_URL?.trim();
  if (apiBase) {
    const wsBase = apiBase.replace(/^http:\/\//, "ws://").replace(/^https:\/\//, "wss://");
    return `${wsBase.replace(/\/$/, "")}/ws/runs/latest`;
  }

  return "ws://127.0.0.1:8001/ws/runs/latest";
}

/**
 * HTTP bootstrap + WebSocket live updates for the Nexus payload (`web` parity).
 */
export function useNexusPayload() {
  const [payload, setPayload] = useState<NexusPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [wsConnected, setWsConnected] = useState(false);

  useEffect(() => {
    let cancelled = false;

    fetchNexusPayload()
      .then((data) => {
        if (!cancelled) {
          setPayload(data);
          setError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setPayload(null);
          setError(e instanceof Error ? e : new Error(String(e)));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let closed = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;

    const wsEndpoint = resolveFlowWsUrl();
    let attempt = 0;

    const cleanup = () => {
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (socket) socket.close();
      socket = null;
    };

    const connect = () => {
      if (closed) return;
      cleanup();
      socket = new WebSocket(wsEndpoint);

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as {
            type?: string;
            payload?: NexusPayload;
          };
          if (data.type === "payload" && data.payload) {
            setPayload(data.payload);
            setLoading(false);
            setError(null);
          }
        } catch (e) {
          setError(e instanceof Error ? e : new Error(String(e)));
        }
      };

      socket.onopen = () => {
        attempt = 0;
        setWsConnected(true);
      };

      socket.onclose = () => {
        setWsConnected(false);
        if (closed) return;
        const delay = Math.min(8000, 400 * 2 ** attempt);
        attempt = Math.min(attempt + 1, 6);
        reconnectTimer = window.setTimeout(connect, delay);
      };

      socket.onerror = () => {
        /* reconnect via onclose */
      };
    };

    connect();

    return () => {
      closed = true;
      setWsConnected(false);
      cleanup();
    };
  }, []);

  return { payload, loading, error, wsConnected };
}
