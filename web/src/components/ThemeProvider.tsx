"use client";

import { useEffect } from "react";

const UI_STORAGE_KEY = "aimm-theme-ui";

function getInitialUiVariant(): "v2" | "legacy" {
  if (typeof window === "undefined") return "legacy";
  try {
    const stored = localStorage.getItem(UI_STORAGE_KEY);
    if (stored === "v2" || stored === "legacy") return stored;
  } catch {
    // ignore
  }
  return process.env.NEXT_PUBLIC_AIMM_THEME_V2 === "1" ? "v2" : "legacy";
}

export function setThemeUiVariant(variant: "v2" | "legacy") {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(UI_STORAGE_KEY, variant);
  } catch {
    // ignore
  }
  document.documentElement.classList.toggle("theme-v2", variant === "v2");
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    document.documentElement.classList.remove("light");
    try {
      localStorage.setItem("nexus-theme", "dark");
    } catch {
      // ignore
    }
    const ui = getInitialUiVariant();
    document.documentElement.classList.toggle("theme-v2", ui === "v2");
  }, []);

  return <>{children}</>;
}
