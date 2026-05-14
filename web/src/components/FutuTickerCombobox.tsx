"use client";

import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import { getAllStocks, type FutuStockEntry } from "@/data/futuStocks";

// ── Fuzzy match helper ──

function scoreMatches(query: string, entry: FutuStockEntry): number {
  const q = query.toLowerCase().trim();
  if (!q) return 0;
  const code = entry.code.toLowerCase();
  const name = entry.name.toLowerCase();
  const suffix = entry.suffix.toLowerCase();

  // Exact prefix match on code (HK.00700 ← typing "00700" or "hk.007")
  if (code.startsWith(q)) return 100;
  // Code contains query
  if (code.includes(q)) return 80;
  // Search suffix first (short name like "Tencent" or "AAPL")
  if (suffix.startsWith(q)) return 90;
  if (suffix.includes(q)) return 70;
  // Full name match
  if (name.startsWith(q)) return 60;
  if (name.includes(q)) return 40;
  return 0;
}

// ── Component ──

export function FutuTickerCombobox({
  value,
  onChange,
  disabled = false,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(() => {
    // Pre-fill with the name of the current value if known
    const all = getAllStocks();
    const known = all.find((s) => s.code === value);
    return known ? `${known.suffix}` : value;
  });
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const allStocks = useMemo(() => getAllStocks(), []);

  const scored = useMemo(() => {
    if (!query.trim()) return allStocks.slice(0, 50); // show first 50 as default
    const withScores = allStocks
      .map((s) => ({ ...s, score: scoreMatches(query, s) }))
      .filter((s) => s.score > 0)
      .sort((a, b) => b.score - a.score);
    return withScores.slice(0, 80);
  }, [query, allStocks]);

  const displayLabel = useMemo(() => {
    const known = allStocks.find((s) => s.code === value);
    if (known) return `${known.code} — ${known.name}`;
    return value;
  }, [value, allStocks]);

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    const handle = (e: MouseEvent) => {
      if (
        inputRef.current &&
        !inputRef.current.contains(e.target as Node) &&
        listRef.current &&
        !listRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [open]);

  const select = useCallback(
    (code: string) => {
      onChange(code);
      const found = allStocks.find((s) => s.code === code);
      setQuery(found ? found.suffix : code);
      setOpen(false);
      inputRef.current?.focus();
    },
    [onChange, allStocks],
  );

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
    setOpen(true);
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        inputRef.current?.blur();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        const items = listRef.current?.querySelectorAll("[data-ticker-code]");
        if (items && items.length > 0) {
          (items[0] as HTMLElement).focus();
        }
      }
      if (e.key === "Enter" && scored.length === 1) {
        select(scored[0].code);
      }
    },
    [scored, select],
  );

  const handleListKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const items = listRef.current?.querySelectorAll("[data-ticker-code]");
      if (!items || items.length === 0) return;
      const current = document.activeElement;
      const idx = Array.from(items).indexOf(current as HTMLElement);
      if (e.key === "ArrowDown") {
        e.preventDefault();
        const next = Math.min(idx + 1, items.length - 1);
        (items[next] as HTMLElement).focus();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        const prev = Math.max(idx - 1, 0);
        (items[prev] as HTMLElement).focus();
      } else if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        inputRef.current?.focus();
      } else if (e.key === "Enter" && current) {
        e.preventDefault();
        const code = current.getAttribute("data-ticker-code");
        if (code) select(code);
      }
    },
    [select],
  );

  return (
    <div className="relative">
      <input
        ref={inputRef}
        type="text"
        className="w-full rounded-lg border border-[rgba(138,149,166,0.25)] bg-[var(--nexus-surface)] px-3 py-2 font-mono text-[11px] text-[var(--nexus-text)] placeholder-[rgba(138,149,166,0.35)] transition focus:border-[rgba(0,212,170,0.4)] focus:outline-none focus:ring-1 focus:ring-[rgba(0,212,170,0.15)] disabled:opacity-40"
        value={query}
        onChange={handleInputChange}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
        placeholder="Search HK / US stocks… (e.g. Tencent, 00700, AAPL)"
        disabled={disabled}
        autoComplete="off"
        spellCheck={false}
      />

      {open && scored.length > 0 && (
        <div
          ref={listRef}
          className="absolute left-0 right-0 top-full z-50 mt-1 max-h-[280px] overflow-y-auto rounded-lg border border-[rgba(138,149,166,0.2)] bg-[var(--nexus-panel)] shadow-lg"
          onKeyDown={handleListKeyDown}
          role="listbox"
        >
          {scored.map((s) => {
            const selected = s.code === value;
            return (
              <button
                key={s.code}
                type="button"
                data-ticker-code={s.code}
                role="option"
                aria-selected={selected}
                onClick={() => select(s.code)}
                onMouseDown={(e) => e.preventDefault()}
                className={`flex w-full items-center gap-2 px-3 py-1.5 text-left transition ${
                  selected
                    ? "bg-[rgba(0,212,170,0.08)]"
                    : "hover:bg-[rgba(138,149,166,0.06)]"
                }`}
              >
                <span className="shrink-0 font-mono text-[10px] text-[rgba(226,232,240,0.45)]">
                  {s.code}
                </span>
                <span className="truncate text-[10px] text-[rgba(226,232,240,0.75)]">
                  {s.name}
                </span>
                <span className="ml-auto shrink-0 font-mono text-[9px] text-[rgba(138,149,166,0.4)]">
                  {s.suffix}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {open && query.trim() && scored.length === 0 && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 rounded-lg border border-[rgba(138,149,166,0.2)] bg-[var(--nexus-panel)] px-3 py-2 text-[10px] text-[var(--nexus-muted)]">
          No stocks match &quot;{query}&quot;
        </div>
      )}

      {/* Display the selected value if dropdown is closed */}
      {!open && value && (
        <p className="mt-0.5 truncate font-mono text-[9px] text-[rgba(138,149,166,0.5)]">
          {displayLabel}
        </p>
      )}
    </div>
  );
}
