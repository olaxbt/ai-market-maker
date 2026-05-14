import { Suspense } from "react";
import Script from "next/script";
import { StudioThemeGuard } from "./StudioThemeGuard";

export default function StudioLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="studio-scope studio-modern min-h-screen h-screen flex flex-col">
      {/* Studio runs in a light, Minara-like skin. Prevent the Nexus boot overlay + theme flash. */}
      <Script id="studio-preflight" strategy="beforeInteractive">
        {`
          try { sessionStorage.setItem("nexus_boot_done_v1", "1"); } catch {}
          try { document.documentElement.classList.add("light"); } catch {}
        `}
      </Script>
      <StudioThemeGuard />

      <header className="shrink-0 border-b border-[rgba(15,23,42,0.08)] bg-[rgba(255,255,255,0.72)] backdrop-blur px-4 py-3">
        <div className="mx-auto flex w-full items-center justify-between gap-3 px-2">
          <div className="min-w-0">
            <div className="studio-h1">Studio</div>
            <div className="mt-0.5 text-[13px] text-[rgba(15,23,42,0.62)]">
              Quant OS chat workspace.
            </div>
          </div>
          <div className="text-[12px] text-[rgba(15,23,42,0.55)]">
            Local sessions • receipts-ready
          </div>
        </div>
      </header>

      {/* Let inner panels control their own scrolling (chat feels like Claude/IDE). */}
      <div className="min-h-0 flex-1 overflow-hidden">
        <Suspense
          fallback={
            <div className="flex h-full items-center justify-center text-[12px] text-[rgba(15,23,42,0.55)]">
              Loading studio…
            </div>
          }
        >
          <div className="h-full min-h-0">
            {children}
          </div>
        </Suspense>
      </div>
    </div>
  );
}

