/** Formats an ISO-8601 timestamp for display (en-GB, 24h). */
export function formatTraceTime(ts: string) {
  try {
    return new Date(ts).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return ts;
  }
}
