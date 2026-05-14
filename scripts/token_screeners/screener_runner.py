"""
Screener Runner - runs VCP and Wyckoff scanners on schedule (one or many variants)
====================================================================================

Two modes:
    1. DAEMON MODE  (default)
       Loops forever, runs both scanners every --interval seconds (default 300 = 5 min).
       Use this when you want a single always-on process.

    2. CRON MODE    (--once)
       Runs each scanner exactly once and exits cleanly.
       Use this when invoking from Windows Task Scheduler every 5 min.

Variant support:
    Each scanner has multiple parameter variants (defined in vcp_variants.py
    and wyckoff_variants.py). You can run any subset via --vcp-variants and
    --wy-variants. Each variant produces its own universe JSON file:
        v1_baseline              -> vcp_universe.json (legacy filename)
        v2_strict_crypto         -> vcp_universe_v2_strict_crypto.json
        v3_crypto_aggressive     -> vcp_universe_v3_crypto_aggressive.json
        ...
    Downstream consumers can call vcp_scanner.load_universe(variant_name=...)
    or wyckoff_scanner.load_universe_by_phase(variant_name=...) to read.

Both scanners read 5m candles from `Screened_data/` (populated by
screened_data_lake.py) and write their universe JSONs to `screened_result/`.

Usage:
    # Cron mode, baseline variant only (production default)
    python screener_runner.py --once

    # Cron mode, a specific non-baseline variant
    python screener_runner.py --once --vcp-variants v2_strict_crypto

    # Cron mode, multiple variants in parallel (each writes its own JSON)
    python screener_runner.py --once --vcp-variants v1_baseline,v2_strict_crypto

    # Cron mode, ALL variants (heavy - every defined variant runs)
    python screener_runner.py --once --vcp-variants all --wy-variants all

    # Daemon mode, 5-min loop
    python screener_runner.py

    # Single screener only
    python screener_runner.py --once --vcp-only
    python screener_runner.py --once --wyckoff-only

    # Override scan timeframe
    python screener_runner.py --once --tf 4h

Logging:
    Writes to stdout by default. Use --log-file PATH to also append to a file.

Windows Task Scheduler hookup (cron-mode):
    Action         : Start a program
    Program/script : C:\\Users\\AreixPC\\miniconda3\\python.exe
    Add arguments  : C:\\Users\\AreixPC\\Desktop\\Pro\\screener_runner.py --once
    Start in       : C:\\Users\\AreixPC\\Desktop\\Pro
    Trigger        : Daily, repeat task every 5 minutes for 1 day
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Same directory as vcp_scanner / wyckoff_scanner (for imports and optional *_variants.py)
_SCREENERS_DIR = Path(__file__).resolve().parent
if str(_SCREENERS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCREENERS_DIR))


def _now_utc8() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")


def _log(msg: str, log_file: str | None = None):
    line = f"[{_now_utc8()}] {msg}"
    print(line, flush=True)
    if log_file:
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass


def _resolve_vcp_variants(requested: list[str]) -> list[tuple[str, dict]]:
    """Convert variant name list to [(name, params)] pairs. 'all' expands to
    every variant in the registry. Empty/None -> baseline only."""
    try:
        from vcp_variants import VCP_VARIANTS, get_variant
    except Exception:
        return [("v1_baseline", None)]  # fall back to scanner DEFAULT_PARAMS
    if not requested:
        return [("v1_baseline", get_variant("v1_baseline"))]
    if any(r.lower() == "all" for r in requested):
        return [(n, get_variant(n)) for n in VCP_VARIANTS]
    out = []
    for n in requested:
        if n in VCP_VARIANTS:
            out.append((n, get_variant(n)))
        else:
            print(
                f"WARNING: unknown VCP variant '{n}' (known: {list(VCP_VARIANTS)})", file=sys.stderr
            )
    if not out:
        out = [("v1_baseline", get_variant("v1_baseline"))]
    return out


def _resolve_wy_variants(requested: list[str]) -> list[tuple[str, dict]]:
    try:
        from wyckoff_variants import WYCKOFF_VARIANTS, get_variant
    except Exception:
        return [("v1_baseline", None)]
    if not requested:
        return [("v1_baseline", get_variant("v1_baseline"))]
    if any(r.lower() == "all" for r in requested):
        return [(n, get_variant(n)) for n in WYCKOFF_VARIANTS]
    out = []
    for n in requested:
        if n in WYCKOFF_VARIANTS:
            out.append((n, get_variant(n)))
        else:
            print(
                f"WARNING: unknown Wyckoff variant '{n}' (known: {list(WYCKOFF_VARIANTS)})",
                file=sys.stderr,
            )
    if not out:
        out = [("v1_baseline", get_variant("v1_baseline"))]
    return out


def run_vcp(
    scan_tf: str, variant_name: str, variant_params: dict | None, log_file: str | None = None
) -> bool:
    try:
        from vcp_scanner import DEFAULT_PARAMS as VCP_P
        from vcp_scanner import scan_universe as vcp_scan

        params = dict(variant_params if variant_params is not None else VCP_P)
        params["scan_tf"] = scan_tf
        t0 = time.time()
        out = vcp_scan(params=params, verbose=False)
        elapsed = time.time() - t0
        _log(
            f"[VCP/{variant_name:<22}] OK  scanned={out['n_tokens_scanned']:>4}  "
            f"strict={out['n_passed_strict']:>3}  relaxed={out['n_passed_relaxed']:>3}  "
            f"elapsed={elapsed:5.1f}s",
            log_file,
        )
        return True
    except Exception as e:
        _log(f"[VCP/{variant_name}] FAIL  {type(e).__name__}: {e}", log_file)
        traceback.print_exc()
        return False


def run_wyckoff(
    scan_tf: str, variant_name: str, variant_params: dict | None, log_file: str | None = None
) -> bool:
    try:
        from wyckoff_scanner import DEFAULT_PARAMS as WY_P
        from wyckoff_scanner import scan_universe as wy_scan

        params = dict(variant_params if variant_params is not None else WY_P)
        params["scan_tf"] = scan_tf
        t0 = time.time()
        out = wy_scan(params=params, verbose=False)
        elapsed = time.time() - t0
        pc = out.get("phase_counts", {})
        _log(
            f"[Wyckoff/{variant_name:<22}] OK  scanned={out['n_scanned']:>4}  "
            f"A={pc.get('A', 0):>3} B={pc.get('B', 0):>3} C={pc.get('C', 0):>3} "
            f"D={pc.get('D', 0):>3} E={pc.get('E', 0):>3}  "
            f"elapsed={elapsed:5.1f}s",
            log_file,
        )
        return True
    except Exception as e:
        _log(f"[Wyckoff/{variant_name}] FAIL  {type(e).__name__}: {e}", log_file)
        traceback.print_exc()
        return False


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(
        description="Run VCP + Wyckoff screeners on schedule (one or many variants).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--once", action="store_true", help="Run scanners exactly once and exit (cron mode)."
    )
    ap.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Daemon-mode loop interval in seconds (default 300 = 5 min).",
    )
    ap.add_argument("--tf", default="1h", help="Scan timeframe: 5m | 15m | 1h | 4h (default 1h).")
    ap.add_argument("--vcp-only", action="store_true", help="Skip Wyckoff scan.")
    ap.add_argument("--wyckoff-only", action="store_true", help="Skip VCP scan.")
    ap.add_argument(
        "--vcp-variants",
        default="v1_baseline",
        help="Comma-separated VCP variant names, or 'all'. Default: v1_baseline only.",
    )
    ap.add_argument(
        "--wy-variants",
        default="v1_baseline",
        help="Comma-separated Wyckoff variant names, or 'all'. Default: v1_baseline only.",
    )
    ap.add_argument(
        "--log-file", default=None, help="Append all log lines to this file as well as stdout."
    )
    args = ap.parse_args()

    if args.vcp_only and args.wyckoff_only:
        print("Cannot use --vcp-only and --wyckoff-only together.", file=sys.stderr)
        sys.exit(2)

    vcp_var_list = _resolve_vcp_variants(
        [s.strip() for s in args.vcp_variants.split(",") if s.strip()]
    )
    wy_var_list = _resolve_wy_variants(
        [s.strip() for s in args.wy_variants.split(",") if s.strip()]
    )

    def one_cycle():
        if not args.wyckoff_only:
            for vname, vparams in vcp_var_list:
                run_vcp(args.tf, vname, vparams, args.log_file)
        if not args.vcp_only:
            for wname, wparams in wy_var_list:
                run_wyckoff(args.tf, wname, wparams, args.log_file)

    _log(
        f"=== Screener Runner starting "
        f"({'CRON / single shot' if args.once else f'DAEMON / {args.interval}s loop'}) ===",
        args.log_file,
    )
    _log(
        f"    scan_tf={args.tf}  vcp_only={args.vcp_only}  wyckoff_only={args.wyckoff_only}",
        args.log_file,
    )
    _log(f"    vcp_variants={[n for n, _ in vcp_var_list]}", args.log_file)
    _log(f"    wy_variants ={[n for n, _ in wy_var_list]}", args.log_file)

    if args.once:
        one_cycle()
        _log("Single-shot complete. Exiting.", args.log_file)
        return

    cycle = 0
    try:
        while True:
            cycle += 1
            _log(f"--- Cycle #{cycle} ---", args.log_file)
            one_cycle()
            _log(f"Sleeping {args.interval}s until next cycle...", args.log_file)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        _log("Interrupted by user. Shutting down cleanly.", args.log_file)
    except Exception as e:
        _log(f"FATAL  {type(e).__name__}: {e}", args.log_file)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
