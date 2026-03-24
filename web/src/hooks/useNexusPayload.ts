"use client";

import { useEffect, useState } from "react";
import { fetchNexusPayload } from "@/lib/api/traces";
import type { NexusPayload } from "@/types/nexus-payload";

export function useNexusPayload() {
  const [payload, setPayload] = useState<NexusPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

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
    const useMock = process.env.NEXT_PUBLIC_USE_MOCK === "1";
    if (useMock) return;

    const wsUrl = process.env.NEXT_PUBLIC_FLOW_WS_URL;
    const base = wsUrl || "ws://127.0.0.1:8001";
    const socket = new WebSocket(`${base}/ws/runs/latest`);
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
    socket.onerror = () => {
      // Keep page usable with the last HTTP payload.
    };
    return () => socket.close();
  }, []);

  return { payload, loading, error };
}
