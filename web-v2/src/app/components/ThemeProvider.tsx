import type { ReactNode } from "react";
import { ThemeProvider as NextThemesProvider } from "next-themes";

/**
 * Persists to localStorage (`aimm-web-v2-theme`). Adds `class="dark"` on `<html>` when dark.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <NextThemesProvider attribute="class" defaultTheme="light" enableSystem={false} storageKey="aimm-web-v2-theme">
      {children}
    </NextThemesProvider>
  );
}
