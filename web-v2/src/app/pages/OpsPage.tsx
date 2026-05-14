import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";
import { Tabs, TabsList, TabsTrigger } from "../components/ui/tabs";
import PaperPage from "./PaperPage";
import InboxPage from "./InboxPage";

export default function OpsPage() {
  const [searchParams] = useSearchParams();
  const [tab, setTab] = useState<"paper" | "queue">(() => {
    try {
      const saved = localStorage.getItem("aimm.ops.active_tab");
      if (saved === "queue" || saved === "paper") return saved;
    } catch {
      // ignore
    }
    return "paper";
  });

  useEffect(() => {
    const q = (searchParams.get("tab") ?? "").trim();
    if (q === "queue" || q === "paper") setTab(q);
  }, [searchParams]);

  useEffect(() => {
    try {
      localStorage.setItem("aimm.ops.active_tab", tab);
    } catch {
      // ignore
    }
  }, [tab]);

  return (
    <div className="flex-1 min-h-0 overflow-auto">
      <div className="px-4 pt-6 sm:px-6">
        <div className="mx-auto w-full max-w-6xl">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="min-w-0">
              <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Operations</div>
              <h2 className="mt-1 text-xl font-semibold tracking-tight">Ops desk</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Paper book (balances, positions, fills) and the operator queue (approve/execute).
              </p>
            </div>
            <Tabs value={tab} onValueChange={(v) => setTab(v as any)}>
              <TabsList>
                <TabsTrigger value="paper">Paper</TabsTrigger>
                <TabsTrigger value="queue">Queue</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </div>
      </div>

      <div className="pt-4">
        {tab === "paper" ? <PaperPage embedded /> : <InboxPage embedded />}
      </div>
    </div>
  );
}

