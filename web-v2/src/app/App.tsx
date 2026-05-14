import { Menu } from "lucide-react";
import { useMemo, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router";
import Navigation from "./components/Navigation";
import ChatView from "./components/ChatView";
import BacktestView from "./components/BacktestView";
import NexusView from "./components/NexusView";
import StudioPage from "./pages/StudioPage";
import StudioV2Page from "./pages/StudioV2Page";
import GetStartedPage from "./pages/GetStartedPage";
import WhatIsThisPage from "./pages/WhatIsThisPage";
import ToolsPage from "./pages/ToolsPage";
import ControlPage from "./pages/ControlPage";
import PlatformLoginPage from "./pages/PlatformLoginPage";
import PlatformProvidersPage from "./pages/PlatformProvidersPage";
import PaperPage from "./pages/PaperPage";
import InboxPage from "./pages/InboxPage";
import FeedRedirectPage from "./pages/FeedRedirectPage";
import LeadpageRedirectPage from "./pages/LeadpageRedirectPage";
import LeadpageProviderRedirectPage from "./pages/LeadpageProviderRedirectPage";
import LeaderboardProviderPage from "./pages/LeaderboardProviderPage";
import PublicProviderPage from "./pages/PublicProviderPage";
import LeaderboardV2OriginalPage from "./pages/LeaderboardV2OriginalPage";
import AccountPage from "./pages/AccountPage";
import SettingsPage from "./pages/SettingsPage";
import WorkspacePage from "./pages/WorkspacePage";
import BacktestRedirectPage from "./pages/BacktestRedirectPage";
import StudioStrategiesRedirectPage from "./pages/StudioStrategiesRedirectPage";
import AgentDetailPage from "./pages/AgentDetailPage";
import NotFoundPage from "./pages/NotFoundPage";
import BacktestsPage from "./pages/BacktestsPage";
import GuidesPage from "./pages/GuidesPage";
import { ThemeToggle } from "./components/ThemeToggle";

/** Short page title for the top bar (navigation lives in the left sidebar only). */
function routeTitle(pathname: string): string {
  if (pathname === "/studio" || pathname.startsWith("/studio/")) return "Studio";
  if (pathname === "/leaderboard" || pathname.startsWith("/leaderboard")) return "Leaderboard";
  if (pathname === "/console") return "Nexus Console";
  if (pathname === "/control") return "Control Center";
  if (pathname === "/backtests") return "Backtests";
  if (pathname === "/workspace") return "Workspace";
  if (pathname === "/ops") return "Operations";
  if (pathname === "/guides") return "Guides";
  if (pathname === "/get-started") return "Get Started";
  if (pathname === "/tools") return "Tools";
  if (pathname === "/what-is-this") return "What is AIMM";
  if (pathname === "/trade") return "Trade hub";
  if (pathname.startsWith("/platform/providers")) return "Provider keys";
  if (pathname === "/platform/login") return "Platform login";
  if (pathname === "/paper") return "Paper";
  if (pathname === "/inbox") return "Queue";
  if (pathname === "/account") return "Account";
  if (pathname === "/settings") return "Settings";
  if (pathname.startsWith("/agent/")) return "Agent detail";
  if (pathname.startsWith("/p/")) return "Provider";
  if (pathname === "/v2/chat") return "Chat";
  if (pathname === "/v2/leaderboard") return "Backtest view";
  return "Workspace";
}

function AppShell({ navOpen, setNavOpen }: { navOpen: boolean; setNavOpen: (v: boolean) => void }) {
  const { pathname } = useLocation();
  const title = useMemo(() => routeTitle(pathname), [pathname]);

  return (
    <div className="h-screen flex overflow-hidden bg-background text-foreground">
      <Navigation isOpen={navOpen} onToggle={() => setNavOpen(!navOpen)} />

      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        <header className="border-b border-border bg-background px-3 py-2.5 sm:px-4 flex items-center gap-3 shrink-0">
          <button
            type="button"
            onClick={() => setNavOpen(!navOpen)}
            className="lg:hidden p-2 rounded-lg hover:bg-accent transition-colors shrink-0"
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="min-w-0 flex-1">
            <h1 className="text-base font-semibold tracking-tight truncate">{title}</h1>
            <p className="text-[11px] text-muted-foreground truncate">AI Market Maker</p>
          </div>
          <ThemeToggle />
        </header>

        <Routes>
          <Route path="/" element={<Navigate to="/leaderboard" replace />} />
          <Route path="/studio" element={<StudioV2Page />} />
          <Route path="/studio-legacy" element={<StudioPage />} />
          <Route path="/backtests" element={<BacktestsPage />} />
          <Route path="/leaderboard" element={<LeaderboardV2OriginalPage />} />
          <Route path="/console" element={<NexusView />} />
          <Route path="/guides" element={<GuidesPage />} />
          <Route path="/v2/chat" element={<ChatView />} />
          <Route path="/v2/leaderboard" element={<BacktestView />} />

          <Route path="/control" element={<ControlPage />} />
          <Route path="/get-started" element={<Navigate to="/guides?section=get-started" replace />} />
          <Route path="/tools" element={<ToolsPage />} />
          <Route path="/what-is-this" element={<Navigate to="/guides?section=what-is-aimm" replace />} />
          <Route path="/trade" element={<Navigate to="/console" replace />} />
          <Route path="/platform/providers" element={<PlatformProvidersPage />} />
          <Route path="/platform/login" element={<PlatformLoginPage />} />
          <Route path="/backtest" element={<BacktestRedirectPage />} />
          <Route path="/account" element={<Navigate to="/workspace" replace />} />
          <Route path="/settings" element={<Navigate to="/workspace" replace />} />
          <Route path="/paper" element={<Navigate to="/console?view=monitor" replace />} />
          <Route path="/inbox" element={<Navigate to="/console?view=monitor" replace />} />
          <Route path="/workspace" element={<WorkspacePage />} />
          <Route path="/ops" element={<Navigate to="/console?view=monitor" replace />} />
          <Route path="/feed" element={<FeedRedirectPage />} />
          <Route path="/studio/strategies" element={<StudioStrategiesRedirectPage />} />
          <Route path="/leaderboard/providers/:provider" element={<LeaderboardProviderPage />} />
          <Route path="/leadpage" element={<LeadpageRedirectPage />} />
          <Route path="/leadpage/providers/:provider" element={<LeadpageProviderRedirectPage />} />
          <Route path="/p/:provider" element={<PublicProviderPage />} />
          <Route path="/agent/:nodeId" element={<AgentDetailPage />} />

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </div>
    </div>
  );
}

export default function App() {
  const [navOpen, setNavOpen] = useState(false);
  return <AppShell navOpen={navOpen} setNavOpen={setNavOpen} />;
}
