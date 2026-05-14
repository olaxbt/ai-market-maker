"use client";

import { useEffect, useState } from "react";
import { fetchNexusPayloadWithSource } from "@/lib/api/traces";
import type { NexusPayload } from "@/types/nexus-payload";
import mockTraces from "@/data/mock-traces.json";

function resolveFlowWsUrl(): string {
  const explicit = process.env.NEXT_PUBLIC_FLOW_WS_URL?.trim();
  if (explicit) {
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
  /** `mock` | `mock-fallback` | `mock-offline` | `live` | null — from /api/traces, client mock, or WS */
  const [traceDataSource, setTraceDataSource] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    // Live Flow by default. Set NEXT_PUBLIC_USE_MOCK=1 for bundled demo topology (no Flow / no LLM required).
    const useMock = process.env.NEXT_PUBLIC_USE_MOCK?.trim() === "1";
    if (useMock) {
      setPayload(mockTraces as NexusPayload);
      setTraceDataSource("mock");
      setError(null);
      setLoading(false);
      setWsConnected(false);
      return () => {
        cancelled = true;
      };
    }

    fetchNexusPayloadWithSource()
      .then(({ payload: data, dataSource }) => {
        if (!cancelled) {
          setPayload(data);
          setTraceDataSource(dataSource ?? "live");
          setError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setPayload(mockTraces as NexusPayload);
          setTraceDataSource("mock-offline");
          setError(null);
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
    const useMock = process.env.NEXT_PUBLIC_USE_MOCK?.trim() === "1";
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
            setTraceDataSource("live");
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
        // Reconnect via onclose
      };
    };

    connect();

    return () => {
      closed = true;
      setWsConnected(false);
      cleanup();
    };
  }, []);

  return { payload, loading, error, wsConnected, traceDataSource };
}
