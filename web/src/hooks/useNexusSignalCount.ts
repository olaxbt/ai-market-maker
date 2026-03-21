"use client";

import { useEffect, useRef, useState } from "react";
import type { MessageLogEntry } from "@/types/nexus-payload";

const PARTICLE_INTERVAL_MS = 6000;

/** Hub particle intensity from `message_log`, trace count, and a slow timer. */
export function useNexusSignalCount(
  messageLog: MessageLogEntry[] | undefined,
  tracesLength: number,
) {
  const [signalCount, setSignalCount] = useState(0);
  const messageLogBoostRef = useRef(false);

  useEffect(() => {
    if (!messageLog?.length || messageLogBoostRef.current) return;
    messageLogBoostRef.current = true;
    const n = Math.min(12, Math.ceil(messageLog.length / 2));
    setSignalCount((c) => c + n);
  }, [messageLog]);

  useEffect(() => {
    if (tracesLength === 0) return;
    setSignalCount((c) => c + 1);
  }, [tracesLength]);

  useEffect(() => {
    const t = setInterval(() => setSignalCount((c) => c + 1), PARTICLE_INTERVAL_MS);
    return () => clearInterval(t);
  }, []);

  return signalCount;
}
