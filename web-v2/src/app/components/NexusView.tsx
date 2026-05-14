import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router";
import { NexusLegacyConsole } from "./NexusLegacyConsole";

export default function NexusView() {
  const location = useLocation();
  const navigate = useNavigate();

  // Keep legacy behavior: Console "Research" was merged into Studio chat.
  useEffect(() => {
    const qs = new URLSearchParams(location.search);
    const v = (qs.get("view") ?? "").trim();
    if (v !== "research") return;
    const run = (qs.get("run") ?? "").trim();
    navigate(run ? `/studio?run=${encodeURIComponent(run)}` : "/studio", { replace: true });
  }, [location.search, navigate]);

  return <NexusLegacyConsole />;
}
