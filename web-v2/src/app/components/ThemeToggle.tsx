import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { cn } from "./ui/utils";

export function ThemeToggle({ className }: { className?: string }) {
  const { setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className={cn("h-8 w-[76px] shrink-0 rounded-lg bg-muted/50", className)} aria-hidden />
    );
  }

  const mode = resolvedTheme === "dark" ? "dark" : "light";

  const active = "bg-background text-foreground shadow-sm border border-border/60";
  const idle =
    "text-muted-foreground hover:bg-background/70 hover:text-foreground border border-transparent";

  return (
    <div className={cn("inline-flex shrink-0 rounded-lg border border-border bg-muted/40 p-0.5", className)}>
        <button
          type="button"
          title="Light"
          aria-label="Light theme"
          onClick={() => setTheme("light")}
          className={cn(
            "cursor-pointer inline-flex h-7 w-9 items-center justify-center rounded-[6px] transition-colors",
            mode === "light" ? active : idle,
          )}
        >
          <Sun className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          title="Dark"
          aria-label="Dark theme"
          onClick={() => setTheme("dark")}
          className={cn(
            "cursor-pointer inline-flex h-7 w-9 items-center justify-center rounded-[6px] transition-colors",
            mode === "dark" ? active : idle,
          )}
        >
          <Moon className="h-3.5 w-3.5" />
        </button>
    </div>
  );
}
