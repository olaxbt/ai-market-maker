import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import {
  Activity,
  Crown,
  Medal,
  Search,
  TrendingDown,
  TrendingUp,
  Trophy,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Badge } from "../components/ui/badge";

type Signal = {
  id: number;
  ts: number;
  provider: string;
  kind: string;
  title: string;
  body: string;
  ticker?: string | null;
};

type LeaderboardRow = {
  source?: string;
  ts?: number | null;
  provider?: string | null;
  run_id?: string;
  ticker?: string | null;
  trade_count?: number | null;
  total_return_pct?: number | null;
  /** Excess return vs buy-and-hold (or similar), percent points; absent when no benchmark. */
  change_pct?: number | null;
  sharpe?: number | null;
  max_drawdown_pct?: number | null;
  /** Closed-trade win rate, 0–100. */
  win_rate?: number | null;
  profit_factor?: number | null;
};

type RankedRow = LeaderboardRow & { _rank: number };

function fmtNum(v: unknown, d = 2) {
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(d) : "—";
}
function fmtPct(v: unknown, d = 2) {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(d)}%`;
}
function fmtInt(v: unknown) {
  return typeof v === "number" && Number.isFinite(v) ? Math.round(v).toString() : "—";
}
function fmtTsRel(ts: unknown) {
  if (typeof ts !== "number" || !Number.isFinite(ts)) return "—";
  // API may send unix seconds (≈1e9) or epoch ms (≈1e12+).
  const tMs = ts > 10_000_000_000 ? ts : ts * 1000;
  const s = Math.floor((Date.now() - tMs) / 1000);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

function providerColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return (["#00d4aa", "#22d3ee", "#3b82f6", "#8b5cf6", "#f59e0b", "#ef4444", "#ec4899", "#14b8a6"])[
    Math.abs(hash) % 8
  ];
}

function rankBadge(rank: number) {
  if (rank === 1) {
    return (
      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-yellow-400 to-yellow-600 flex items-center justify-center">
        <Crown className="w-5 h-5 text-white" />
      </div>
    );
  }
  if (rank === 2) {
    return (
      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-gray-300 to-gray-500 flex items-center justify-center">
        <Medal className="w-5 h-5 text-white" />
      </div>
    );
  }
  if (rank === 3) {
    return (
      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center">
        <Medal className="w-5 h-5 text-white" />
      </div>
    );
  }
  return (
    <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center text-muted-foreground font-medium">
      #{rank}
    </div>
  );
}

export default function LeaderboardPage() {
  const location = useLocation();
  const navigate = useNavigate();

  const focus = useMemo(() => {
    const qs = new URLSearchParams(location.search);
    return qs.get("focus") === "signals" ? "signals" : "overview";
  }, [location.search]);

  const providerFilter = useMemo(() => {
    const qs = new URLSearchParams(location.search);
    return (qs.get("provider") ?? "").trim();
  }, [location.search]);

  const [rows, setRows] = useState<LeaderboardRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"return" | "sharpe" | "mdd">("return");
  const [search, setSearch] = useState("");
  const rowsRef = useRef<LeaderboardRow[]>([]);

  const [signals, setSignals] = useState<Signal[] | null>(null);

  useEffect(() => {
    if (focus !== "overview") return;
    let cancelled = false;
    if (rowsRef.current.length === 0) setLoading(true);
    setError(null);
    async function load() {
      try {
        const res = await fetch(`/api/leadpage/leaderboard?limit=100&sort_by=${sortBy}`, {
          cache: "no-store" as any,
        });
        const json = await res.json().catch(() => ({}));
        if (cancelled) return;
        if (!res.ok) throw new Error((json as any)?.error ?? `Failed (${res.status})`);
        const next = Array.isArray((json as any)?.rows) ? (json as any).rows : [];
        if (JSON.stringify(rowsRef.current) !== JSON.stringify(next)) {
          setRows(next);
          rowsRef.current = next;
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Load failed");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    const t = window.setInterval(load, 10_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [focus, sortBy]);

  useEffect(() => {
    if (focus !== "signals") return;
    let cancelled = false;
    async function load() {
      try {
        const qs = new URLSearchParams({ limit: "50" });
        if (providerFilter) qs.set("provider", providerFilter);
        const res = await fetch(`/api/signals/feed?${qs.toString()}`, { cache: "no-store" as any });
        const json = await res.json().catch(() => ({}));
        if (cancelled) return;
        setSignals(Array.isArray((json as any)?.signals) ? ((json as any).signals as Signal[]) : []);
      } catch {
        if (!cancelled) setSignals([]);
      }
    }
    void load();
    const t = window.setInterval(load, 15_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [focus, providerFilter]);

  const ranked = useMemo(() => rows.map((r, i) => ({ ...r, _rank: i + 1 })), [rows]);
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const pf = providerFilter.trim().toLowerCase();
    return ranked.filter((r) => {
      const provider = (r.provider ?? "").toLowerCase();
      if (pf && !provider.includes(pf)) return false;
      if (!q) return true;
      const hay = [r.provider ?? "", r.run_id ?? "", r.ticker ?? ""].join(" ").toLowerCase();
      return hay.includes(q);
    });
  }, [ranked, search, providerFilter]);

  const top3 = useMemo(() => filtered.slice(0, 3), [filtered]);

  function setFocus(next: "overview" | "signals") {
    const qs = new URLSearchParams(location.search);
    if (next === "signals") qs.set("focus", "signals");
    else qs.delete("focus");
    navigate(`/leaderboard?${qs.toString()}`, { replace: true });
  }

  return (
    <div className="flex-1 min-h-0 overflow-auto px-4 py-8 sm:px-6 sm:py-10 2xl:px-10">
      <div className="mx-auto w-full max-w-6xl">
        <Card>
          <CardHeader className="border-b">
            <CardTitle className="text-[16px]">Leaderboard</CardTitle>
            <CardDescription className="text-[12px]">
              Compare published backtest results and inspect live provider signals.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs value={focus} onValueChange={(v) => setFocus(v === "signals" ? "signals" : "overview")}>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <TabsList>
                  <TabsTrigger value="overview">
                    <Trophy className="h-4 w-4" />
                    Results
                  </TabsTrigger>
                  <TabsTrigger value="signals">
                    <Activity className="h-4 w-4" />
                    Signals
                  </TabsTrigger>
                </TabsList>

                <div className="flex flex-wrap items-center gap-2">
                  {focus === "overview" ? (
                    <>
                      <div className="relative w-full sm:w-[360px]">
                        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                          value={search}
                          onChange={(e) => setSearch(e.target.value)}
                          placeholder="Search provider / run / ticker…"
                          className="pl-9"
                        />
                      </div>
                      <div className="inline-flex rounded-xl border border-border bg-card p-1">
                        {(["return", "sharpe", "mdd"] as const).map((k) => (
                          <button
                            key={k}
                            type="button"
                            onClick={() => setSortBy(k)}
                            className={[
                              "rounded-lg px-3 py-1.5 text-[12px] transition",
                              sortBy === k ? "bg-muted/40" : "hover:bg-muted/30",
                            ].join(" ")}
                          >
                            {k === "return" ? "Return" : k === "sharpe" ? "Sharpe" : "Max DD"}
                          </button>
                        ))}
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        {loading ? "…" : `${filtered.length}`}
                      </div>
                    </>
                  ) : (
                    <div className="text-[12px] text-muted-foreground">
                      {providerFilter ? (
                        <>
                          Filtering provider{" "}
                          <span className="font-mono text-foreground/90">{providerFilter}</span>{" "}
                          <Link className="underline" to="/leaderboard?focus=signals">
                            clear
                          </Link>
                        </>
                      ) : (
                        "Global feed"
                      )}
                    </div>
                  )}
                </div>
              </div>

              {error ? (
                <div className="mt-3 rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[12px] text-[rgba(242,92,84,0.95)]">
                  {error}
                </div>
              ) : null}

              <TabsContent value="overview" className="mt-4">
                {top3.length > 0 ? (
                  <div className="mb-4 grid grid-cols-1 gap-3 lg:grid-cols-3">
                    {top3.map((r) => {
                      const provider = r.provider?.trim() || "Anonymous";
                      const initials = provider
                        .split(/[^a-zA-Z0-9]+/)
                        .filter(Boolean)
                        .slice(0, 2)
                        .map((x) => x[0]?.toUpperCase())
                        .join("");
                      const aColor = providerColor(provider);
                      const ret = r.total_return_pct;
                      const ok = typeof ret === "number" && Number.isFinite(ret);
                      const pos = ok && ret! >= 0;
                      const chTop = r.change_pct;
                      const okChTop = typeof chTop === "number" && Number.isFinite(chTop);
                      const posChTop = okChTop && chTop! >= 0;
                      const to = `/leaderboard/providers/${encodeURIComponent(provider)}${
                        r.run_id ? `?run=${encodeURIComponent(r.run_id)}` : ""
                      }`;
                      return (
                        <Card
                          key={`${provider}:${r.run_id ?? "norun"}:${r._rank}`}
                          className={[
                            "cursor-pointer",
                            r._rank === 1
                              ? "border-yellow-500/50"
                              : r._rank === 2
                                ? "border-gray-400/40"
                                : "border-orange-500/40",
                          ].join(" ")}
                          onClick={() => navigate(to)}
                        >
                          <CardHeader className="gap-3">
                            <div className="flex items-center justify-between gap-3">
                              {rankBadge(r._rank)}
                              <Badge variant="outline">{r.source ?? "provider"}</Badge>
                            </div>
                            <div className="flex items-center gap-3">
                              <div
                                className="w-12 h-12 rounded-full flex items-center justify-center text-primary-foreground font-semibold"
                                style={{ backgroundColor: aColor }}
                              >
                                {initials || provider.charAt(0).toUpperCase()}
                              </div>
                              <div className="min-w-0">
                                <div className="truncate font-semibold">{provider}</div>
                                <div className="text-xs text-muted-foreground truncate">
                                  run {r.run_id ?? "—"}
                                </div>
                              </div>
                            </div>
                          </CardHeader>
                          <CardContent className="pt-0">
                            <div className="grid grid-cols-3 gap-2">
                              <div className="rounded-lg border bg-muted/20 p-2">
                                <div className="text-[10px] text-muted-foreground">Total return</div>
                                <div className={["font-semibold tabular-nums", pos ? "text-[rgba(0,212,170,0.92)]" : "text-[rgba(242,92,84,0.95)]"].join(" ")}>
                                  {fmtPct(r.total_return_pct, 2)}
                                </div>
                              </div>
                              <div className="rounded-lg border bg-muted/20 p-2">
                                <div className="text-[10px] text-muted-foreground">Change</div>
                                <div
                                  className={[
                                    "font-semibold tabular-nums",
                                    !okChTop
                                      ? "text-muted-foreground"
                                      : posChTop
                                        ? "text-[rgba(0,212,170,0.92)]"
                                        : "text-[rgba(242,92,84,0.95)]",
                                  ].join(" ")}
                                >
                                  {fmtPct(chTop, 2)}
                                </div>
                              </div>
                              <div className="rounded-lg border bg-muted/20 p-2">
                                <div className="text-[10px] text-muted-foreground">Win rate</div>
                                <div className="font-mono tabular-nums">{fmtPct(r.win_rate, 1)}</div>
                              </div>
                              <div className="rounded-lg border bg-muted/20 p-2">
                                <div className="text-[10px] text-muted-foreground">Trades</div>
                                <div className="font-mono tabular-nums">{fmtInt(r.trade_count)}</div>
                              </div>
                              <div className="rounded-lg border bg-muted/20 p-2">
                                <div className="text-[10px] text-muted-foreground">Max DD</div>
                                <div className="font-mono tabular-nums">{fmtNum(r.max_drawdown_pct, 2)}</div>
                              </div>
                              <div className="rounded-lg border bg-muted/20 p-2">
                                <div className="text-[10px] text-muted-foreground">Sharpe</div>
                                <div className="font-mono tabular-nums">{fmtNum(r.sharpe, 2)}</div>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
                ) : null}

                <div className="rounded-xl border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-10">#</TableHead>
                        <TableHead>Provider</TableHead>
                        <TableHead className="text-right">Total return</TableHead>
                        <TableHead className="text-right">Change</TableHead>
                        <TableHead className="text-right">Win rate</TableHead>
                        <TableHead className="text-right">Trades</TableHead>
                        <TableHead className="text-right">Max DD</TableHead>
                        <TableHead className="text-right">Sharpe</TableHead>
                        <TableHead className="text-right">When</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {!loading && filtered.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={9} className="py-10 text-center text-muted-foreground">
                            No results yet.
                          </TableCell>
                        </TableRow>
                      ) : null}
                      {filtered.map((r) => {
                        const provider = r.provider?.trim() || "Anonymous";
                        const aChar = provider.charAt(0).toUpperCase();
                        const aColor = providerColor(provider);
                        const ret = r.total_return_pct;
                        const ok = typeof ret === "number" && Number.isFinite(ret);
                        const pos = ok && ret! >= 0;
                        const ch = r.change_pct;
                        const okCh = typeof ch === "number" && Number.isFinite(ch);
                        const posCh = okCh && ch! >= 0;
                        const to = `/leaderboard/providers/${encodeURIComponent(provider)}${
                          r.run_id ? `?run=${encodeURIComponent(r.run_id)}` : ""
                        }`;
                        return (
                          <TableRow
                            key={`${r.source ?? "x"}:${provider}:${r.run_id ?? "norun"}`}
                            className="cursor-pointer"
                            onClick={() => navigate(to)}
                          >
                            <TableCell className="font-mono text-muted-foreground">{r._rank}</TableCell>
                            <TableCell>
                              <div className="flex items-center gap-2.5">
                                <span
                                  className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-[12px] font-bold"
                                  style={{ backgroundColor: `${aColor}22`, color: aColor }}
                                >
                                  {aChar}
                                </span>
                                <div className="flex min-w-0 flex-col leading-tight">
                                  <span className="truncate text-[13px] font-medium">{provider}</span>
                                  <span className="truncate text-xs text-muted-foreground">
                                    {r.run_id ?? "—"} · {r.source ?? "provider"}
                                  </span>
                                </div>
                              </div>
                            </TableCell>
                            <TableCell
                              className={[
                                "text-right font-semibold tabular-nums",
                                pos ? "text-[rgba(0,212,170,0.92)]" : "text-[rgba(242,92,84,0.95)]",
                              ].join(" ")}
                            >
                              <span className="inline-flex items-center justify-end gap-1">
                                {typeof ret === "number" ? (
                                  pos ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />
                                ) : null}
                                {fmtPct(ret, 2)}
                              </span>
                            </TableCell>
                            <TableCell
                              className={[
                                "text-right font-semibold tabular-nums",
                                !okCh
                                  ? "text-muted-foreground"
                                  : posCh
                                    ? "text-[rgba(0,212,170,0.92)]"
                                    : "text-[rgba(242,92,84,0.95)]",
                              ].join(" ")}
                            >
                              <span className="inline-flex items-center justify-end gap-1">
                                {okCh ? posCh ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" /> : null}
                                {fmtPct(ch, 2)}
                              </span>
                            </TableCell>
                            <TableCell className="text-right font-mono tabular-nums text-muted-foreground">
                              {fmtPct(r.win_rate, 1)}
                            </TableCell>
                            <TableCell className="text-right font-mono tabular-nums text-muted-foreground">
                              {fmtInt(r.trade_count)}
                            </TableCell>
                            <TableCell className="text-right font-mono tabular-nums text-muted-foreground">
                              {fmtNum(r.max_drawdown_pct, 1)}
                            </TableCell>
                            <TableCell className="text-right font-mono tabular-nums text-muted-foreground">
                              {fmtNum(r.sharpe, 2)}
                            </TableCell>
                            <TableCell className="text-right text-xs text-muted-foreground">
                              {fmtTsRel(r.ts)}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              </TabsContent>

              <TabsContent value="signals" className="mt-4">
                {signals === null ? (
                  <div className="rounded-xl border bg-card p-6 text-[12px] text-muted-foreground">
                    Loading signals…
                  </div>
                ) : signals.length === 0 ? (
                  <div className="rounded-xl border bg-card p-6 text-[12px] text-muted-foreground">
                    No signals yet.
                  </div>
                ) : (
                  <div className="flex flex-col gap-2">
                    {signals.map((s) => (
                      <Card key={s.id} className="gap-3">
                        <CardHeader className="pb-0">
                          <CardTitle className="text-[13px]">{s.title}</CardTitle>
                          <CardDescription className="text-[11px]">
                            <span className="mr-2 rounded-md border border-border bg-muted/20 px-2 py-0.5 text-[10px] uppercase tracking-[0.14em]">
                              {s.kind}
                            </span>
                            {s.ticker ? (
                              <span className="font-mono text-muted-foreground">{s.ticker}</span>
                            ) : null}
                            <span className="ml-2 text-muted-foreground">{fmtTsRel(s.ts)}</span>
                          </CardDescription>
                        </CardHeader>
                        <CardContent className="pt-0">
                          {s.body ? (
                            <p className="whitespace-pre-wrap break-words text-[12px] text-muted-foreground">
                              {s.body}
                            </p>
                          ) : null}
                          <div className="mt-2 text-[11px] text-muted-foreground">
                            <Link className="underline" to={`/leaderboard/providers/${encodeURIComponent(s.provider)}`}>
                              {s.provider}
                            </Link>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

