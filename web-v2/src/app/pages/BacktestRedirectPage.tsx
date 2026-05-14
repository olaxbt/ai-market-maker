import { useEffect } from "react";
import { useNavigate } from "react-router";

/** Legacy deep-link: send users to the Backtests workflow page. */
export default function BacktestRedirectPage() {
  const navigate = useNavigate();
  useEffect(() => {
    navigate("/backtests", { replace: true });
  }, [navigate]);
  return (
    <div className="flex-1 min-h-0 overflow-auto p-6">
      <div className="mx-auto max-w-2xl rounded-2xl border border-border bg-card p-6 text-[12px] text-muted-foreground">
        Opening Backtests…
      </div>
    </div>
  );
}

