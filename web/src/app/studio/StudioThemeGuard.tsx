"use client";

import { useEffect } from "react";

export function StudioThemeGuard() {
  useEffect(() => {
    const prevTheme = (() => {
      try {
        return localStorage.getItem("nexus-theme");
      } catch {
        return null;
      }
    })();
    const prevLight = document.documentElement.classList.contains("light");

    // Ensure Studio is light while mounted.
    try {
      localStorage.setItem("nexus-theme", "light");
    } catch {}
    document.documentElement.classList.add("light");

    return () => {
      // Restore prior theme when leaving Studio (fix "navigation feels weird").
      try {
        if (prevTheme === "dark" || prevTheme === "light") {
          localStorage.setItem("nexus-theme", prevTheme);
          document.documentElement.classList.toggle("light", prevTheme === "light");
          return;
        }
      } catch {
        // ignore
      }
      // Fallback: restore previous DOM state.
      document.documentElement.classList.toggle("light", prevLight);
    };
  }, []);

  return null;
}

