"use client";

import { useEffect, useState } from "react";

export function useNowSec(tickMs = 1000): number {
  const [now, setNow] = useState(() => Math.floor(Date.now() / 1000));
  useEffect(() => {
    const id = window.setInterval(() => setNow(Math.floor(Date.now() / 1000)), tickMs);
    return () => window.clearInterval(id);
  }, [tickMs]);
  return now;
}
