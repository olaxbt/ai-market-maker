/** Fetch latest Nexus payload from Flow (same source as Next `/api/traces`). */

export type NexusPayload = Record<string, unknown>;

/** Flow: `GET /runs/latest/payload?soft=1`; Vite proxies `/api/*` → Flow root. */
const DEFAULT_NEXUS_PAYLOAD_PATH = "/api/runs/latest/payload?soft=1";

const RETRYABLE_STATUS = new Set([502, 503, 504]);

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export interface FetchNexusPayloadOptions {
  maxAttempts?: number;
  baseDelayMs?: number;
}

export async function fetchNexusPayload(
  url: string = DEFAULT_NEXUS_PAYLOAD_PATH,
  options?: FetchNexusPayloadOptions,
): Promise<NexusPayload> {
  const maxAttempts = options?.maxAttempts ?? 8;
  const baseDelayMs = options?.baseDelayMs ?? 400;

  let lastMessage = "unknown error";

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      const res = await fetch(url, { cache: "no-store" });
      if (res.ok) {
        return res.json() as Promise<NexusPayload>;
      }

      lastMessage = `Failed to load nexus payload: ${res.status}`;
      if (attempt < maxAttempts - 1 && RETRYABLE_STATUS.has(res.status)) {
        await sleep(baseDelayMs * 2 ** attempt);
        continue;
      }
      throw new Error(lastMessage);
    } catch (e) {
      const isNetwork =
        e instanceof TypeError || (e instanceof Error && /fetch|network|Failed to fetch/i.test(e.message));
      lastMessage = e instanceof Error ? e.message : String(e);

      if (attempt < maxAttempts - 1 && isNetwork) {
        await sleep(baseDelayMs * 2 ** attempt);
        continue;
      }
      throw e instanceof Error ? e : new Error(lastMessage);
    }
  }

  throw new Error(lastMessage);
}
