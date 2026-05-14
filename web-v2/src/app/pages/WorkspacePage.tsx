import { useEffect, useMemo, useState } from "react";
import { Tabs, TabsList, TabsTrigger } from "../components/ui/tabs";
import { useLocation, useNavigate } from "react-router";
import AccountPage from "./AccountPage";
import SettingsPage from "./SettingsPage";

export default function WorkspacePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [tab, setTab] = useState<"account" | "settings">("account");
  const title = useMemo(() => (tab === "account" ? "Account" : "Settings"), [tab]);

  useEffect(() => {
    const qs = new URLSearchParams(location.search);
    const next = (qs.get("tab") ?? "").trim();
    if (next === "settings") setTab("settings");
    else if (next === "account") setTab("account");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search]);

  return (
    <div className="flex-1 min-h-0 overflow-auto">
      <div className="px-4 pt-6 sm:px-6">
        <div className="mx-auto w-full max-w-6xl">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div className="min-w-0">
              <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Workspace</div>
              <h2 className="mt-1 text-xl font-semibold tracking-tight">{title}</h2>
            </div>
            <Tabs
              value={tab}
              onValueChange={(v) => {
                const vv = v === "settings" ? "settings" : "account";
                setTab(vv);
                navigate(`/workspace?tab=${encodeURIComponent(vv)}`, { replace: true });
              }}
            >
              <TabsList>
                <TabsTrigger value="account">Account</TabsTrigger>
                <TabsTrigger value="settings">Settings</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </div>
      </div>

      <div className="pt-4">
        {tab === "account" ? <AccountPage embedded /> : <SettingsPage />}
      </div>
    </div>
  );
}

