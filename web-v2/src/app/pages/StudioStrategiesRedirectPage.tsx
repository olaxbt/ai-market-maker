import { useEffect } from "react";
import { useNavigate } from "react-router";

export default function StudioStrategiesRedirectPage() {
  const navigate = useNavigate();
  useEffect(() => {
    navigate("/studio", { replace: true });
  }, [navigate]);
  return (
    <div className="flex-1 min-h-0 overflow-auto p-6">
      <div className="mx-auto max-w-2xl rounded-2xl border border-border bg-card p-6 text-[12px] text-muted-foreground">
        Opening Studio…
      </div>
    </div>
  );
}

