import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router";

export default function LeadpageRedirectPage() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const qs = location.search?.replace(/^\?/, "") || "";
    navigate(qs ? `/leaderboard?${qs}` : "/leaderboard", { replace: true });
  }, [location.search, navigate]);

  return (
    <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">
      Opening leaderboard…
    </div>
  );
}

