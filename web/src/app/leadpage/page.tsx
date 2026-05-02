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

export default function LegacyLeadpageIndexRedirect({
  searchParams,
}: {
  searchParams: Record<string, string | string[] | undefined>;
}) {
  const qs = toQuery(searchParams);
  redirect(qs ? `/leaderboard?${qs}` : "/leaderboard");
}
