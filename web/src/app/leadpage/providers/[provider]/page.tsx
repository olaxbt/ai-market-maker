import { redirect } from "next/navigation";

function toQuery(searchParams: Record<string, string | string[] | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(searchParams)) {
    if (v == null) continue;
    if (Array.isArray(v)) v.forEach((x) => q.append(k, x));
    else q.set(k, v);
  }
  return q.toString();
}

export default function LegacyLeadpageProviderRedirect({
  params,
  searchParams,
}: {
  params: { provider: string };
  searchParams: Record<string, string | string[] | undefined>;
}) {
  const base = `/leaderboard/providers/${encodeURIComponent(params.provider)}`;
  const qs = toQuery(searchParams);
  redirect(qs ? `${base}?${qs}` : base);
}
