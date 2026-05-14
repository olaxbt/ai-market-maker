import type { NexusPayload } from "@/types/nexus-payload";

const DEFAULT_TRACES_PATH = "/api/traces";

const RETRYABLE_STATUS = new Set([502, 503, 504]);

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export interface FetchNexusPayloadOptions {
  maxAttempts?: number;
  baseDelayMs?: number;
}

export interface FetchNexusPayloadResult {
  payload: NexusPayload;
  /** From `GET /api/traces` response header `x-flow-data-source` when present */
  dataSource: string | null;
}

/**
 * Fetch the Nexus payload with retries; exposes Flow data source header for UI badges.
 */
export async function fetchNexusPayloadWithSource(
  url: string = DEFAULT_TRACES_PATH,
  options?: FetchNexusPayloadOptions,
): Promise<FetchNexusPayloadResult> {
  const maxAttempts = options?.maxAttempts ?? 8;
  const baseDelayMs = options?.baseDelayMs ?? 400;

  let lastMessage = "unknown error";

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      const res = await fetch(url, { cache: "no-store" });
      if (res.ok) {
        const dataSource = res.headers.get("x-flow-data-source");
        const payload = (await res.json()) as NexusPayload;
        return { payload, dataSource };
      }

      lastMessage = `Failed to load traces: ${res.status}`;
      if (attempt < maxAttempts - 1 && RETRYABLE_STATUS.has(res.status)) {
        await sleep(baseDelayMs * 2 ** attempt);
        continue;
      }
      throw new Error(lastMessage);
    } catch (e) {
      const isNetwork =
        e instanceof TypeError ||
        (e instanceof Error && /fetch|network|Failed to fetch/i.test(e.message));
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

/** @deprecated Prefer fetchNexusPayloadWithSource when you need mock vs live labeling */
export async function fetchNexusPayload(
  url: string = DEFAULT_TRACES_PATH,
  options?: FetchNexusPayloadOptions,
): Promise<NexusPayload> {
  const { payload } = await fetchNexusPayloadWithSource(url, options);
  return payload;
}
