"use client";

import { useState, useEffect, useCallback } from "react";
import { Sun, Moon } from "lucide-react";

const UI_STORAGE_KEY = "aimm-theme-ui";

function getInitialTheme(): "light" | "dark" {
  if (typeof window === "undefined") return "dark";
  const stored = localStorage.getItem("nexus-theme");
  if (stored === "dark" || stored === "light") return stored;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

/** v2 maps web-v2 semantic tokens onto `--nexus-*` (see `src/styles/theme-v2.css`). */
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

/** Persist UI variant and sync `html.theme-v2` (for Control/settings once exposed). */
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
    const t = getInitialTheme();
    document.documentElement.classList.toggle("light", t === "light");
    const ui = getInitialUiVariant();
    document.documentElement.classList.toggle("theme-v2", ui === "v2");
  }, []);

  return (
    <>
      {/* ThemeToggleButton is rendered in header/navigation (not floating). */}
      {children}
    </>
  );
}

export function ThemeToggleButton() {
  const [mounted, setMounted] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">("dark");

  useEffect(() => {
    const t = getInitialTheme();
    setTheme(t);
    document.documentElement.classList.toggle("light", t === "light");
    const ui = getInitialUiVariant();
    document.documentElement.classList.toggle("theme-v2", ui === "v2");
    setMounted(true);
  }, []);

  const toggle = useCallback(() => {
    setTheme((prev) => {
      const next = prev === "light" ? "dark" : "light";
      localStorage.setItem("nexus-theme", next);
      document.documentElement.classList.toggle("light", next === "light");
      return next;
    });
  }, []);

  if (!mounted) return null;

  return (
    <button
      type="button"
      onClick={toggle}
      className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/90 text-[var(--nexus-muted)] shadow-sm backdrop-blur-sm transition hover:text-[var(--nexus-text)]"
      title={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
      aria-label="Toggle color theme"
    >
      {theme === "light" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
    </button>
  );
}
