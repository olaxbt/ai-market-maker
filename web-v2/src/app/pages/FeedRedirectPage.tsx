import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router";

export default function FeedRedirectPage() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const qs = new URLSearchParams(location.search);
    const provider = (qs.get("provider") ?? "").trim();
    const next = new URLSearchParams({ focus: "signals" });
    if (provider) next.set("provider", provider);
    navigate(`/leaderboard?${next.toString()}`, { replace: true });
  }, [location.search, navigate]);

  return (
    <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">
      Opening signals…
    </div>
  );
}

