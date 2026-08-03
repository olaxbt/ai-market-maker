"use client";

import { useEffect, useState } from "react";
import { fetchNexusPayloadWithSource } from "@/lib/api/traces";
import type { NexusPayload } from "@/types/nexus-payload";
import mockTraces from "@/data/mock-traces.json";
import { getFlowApiOrigin } from "@/lib/flowApiOrigin";

function resolveFlowWsUrl(runId: string): string {
  const rid = (runId || "latest").trim() || "latest";
  const explicit = process.env.NEXT_PUBLIC_FLOW_WS_URL?.trim();
  if (explicit) {
    if (explicit.includes("/ws/runs/")) {
      return explicit.replace(/\/ws\/runs\/[^/?#]+/, `/ws/runs/${encodeURIComponent(rid)}`);
    }
    if (explicit.includes("/ws/")) {
      const base = explicit.replace(/\/$/, "");
      return `${base.replace(/\/ws\/.*$/, "")}/ws/runs/${encodeURIComponent(rid)}`;
    }
    return `${explicit.replace(/\/$/, "")}/ws/runs/${encodeURIComponent(rid)}`;
  }

  const apiBase = process.env.NEXT_PUBLIC_FLOW_API_BASE_URL?.trim();
  if (apiBase) {
    const wsBase = apiBase.replace(/^http:\/\//, "ws://").replace(/^https:\/\//, "wss://");
    return `${wsBase.replace(/\/$/, "")}/ws/runs/${encodeURIComponent(rid)}`;
  }

  return `ws://127.0.0.1:8001/ws/runs/${encodeURIComponent(rid)}`;
}

/**
 * @param runId Flow run to follow. Live desk should use `latest-paper` or a concrete
 * `run-…` id. Research panels fetch `/runs/{bt-…}` themselves — do not point Live
 * at `bt-*` so paper and backtest can run in parallel without stream theft.
 */
export function useNexusPayload(runId: string = "latest") {
  const followId = (runId || "latest").trim() || "latest";
  const [payload, setPayload] = useState<NexusPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [traceDataSource, setTraceDataSource] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

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

    setLoading(true);
    const httpUrl =
      followId === "latest"
        ? "/api/traces"
        : `${getFlowApiOrigin()}/runs/${encodeURIComponent(followId)}/payload?soft=true`;

    fetchNexusPayloadWithSource(httpUrl)
      .then(({ payload: data, dataSource }) => {
        if (!cancelled) {
          setPayload(data);
          setTraceDataSource(dataSource ?? "live");
          setError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setPayload(null);
          setTraceDataSource("idle");
          setError(e instanceof Error ? e : new Error(String(e)));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [followId]);

  useEffect(() => {
    const useMock = process.env.NEXT_PUBLIC_USE_MOCK?.trim() === "1";
    if (useMock) return;

    let closed = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    const wsEndpoint = resolveFlowWsUrl(followId);
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
  }, [followId]);

  return { payload, loading, error, wsConnected, traceDataSource, followRunId: followId };
}
