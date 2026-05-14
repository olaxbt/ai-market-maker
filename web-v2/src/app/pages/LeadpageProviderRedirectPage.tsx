import { useEffect } from "react";
import { useLocation, useNavigate, useParams } from "react-router";

export default function LeadpageProviderRedirectPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const params = useParams();
  const provider = params.provider ? String(params.provider) : "";

  useEffect(() => {
    const base = `/leaderboard/providers/${encodeURIComponent(provider)}`;
    const qs = location.search?.replace(/^\?/, "") || "";
    navigate(qs ? `${base}?${qs}` : base, { replace: true });
  }, [location.search, navigate, provider]);

  return (
    <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground">
      Opening provider…
    </div>
  );
}

