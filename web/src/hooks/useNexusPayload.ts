"use client";

import { useEffect, useState } from "react";
import { fetchNexusPayload } from "@/lib/api/traces";
import type { NexusPayload } from "@/types/nexus-payload";
import mockTraces from "@/data/mock-traces.json";

function resolveFlowWsUrl(): string {
  const explicit = process.env.NEXT_PUBLIC_FLOW_WS_URL?.trim();
  if (explicit) {
    // Allow either:
    // - full endpoint: ws(s)://host/ws/runs/latest
    // - base host: ws(s)://host
    if (explicit.includes("/ws/")) return explicit;
    return `${explicit.replace(/\/$/, "")}/ws/runs/latest`;
  }

  const apiBase = process.env.NEXT_PUBLIC_FLOW_API_BASE_URL?.trim();
  if (apiBase) {
    const wsBase = apiBase.replace(/^http:\/\//, "ws://").replace(/^https:\/\//, "wss://");
    return `${wsBase.replace(/\/$/, "")}/ws/runs/latest`;
  }

  return "ws://127.0.0.1:8001/ws/runs/latest";
}

export function useNexusPayload() {
  const [payload, setPayload] = useState<NexusPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [wsConnected, setWsConnected] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const useMock = process.env.NEXT_PUBLIC_USE_MOCK === "1";
    if (useMock) {
      setPayload(mockTraces as NexusPayload);
      setError(null);
      setLoading(false);
      setWsConnected(false);
      return () => {
        cancelled = true;
      };
    }

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
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const useMock = process.env.NEXT_PUBLIC_USE_MOCK === "1";
    if (useMock) return;

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
        // Exponential-ish backoff capped so local dev restarts recover quickly.
        const delay = Math.min(8000, 400 * 2 ** attempt);
        attempt = Math.min(attempt + 1, 6);
        reconnectTimer = window.setTimeout(connect, delay);
      };

      socket.onerror = () => {
        // Keep page usable with the last HTTP payload; reconnect is handled by onclose.
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
