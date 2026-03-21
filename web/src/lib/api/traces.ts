import type { NexusPayload } from "@/types/nexus-payload";

const DEFAULT_TRACES_PATH = "/api/traces";

/** Fetches the Nexus dashboard JSON payload. */
export async function fetchNexusPayload(
  url: string = DEFAULT_TRACES_PATH,
): Promise<NexusPayload> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to load traces: ${res.status}`);
  }
  return res.json() as Promise<NexusPayload>;
}
