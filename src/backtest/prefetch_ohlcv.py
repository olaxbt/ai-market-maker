"""Populate OHLCV CSV cache (Binance/CCXT public) for offline or faster reruns.

Examples::

    uv run python -m backtest.prefetch_ohlcv --symbols BTC/USDT,ETH/USDT --timeframe 1d --limit 200

    AIMM_UNIVERSE_SIZE=5 AIMM_BACKTEST_UNIVERSE_MODE=dynamic \\
      uv run python -m backtest.prefetch_ohlcv --dynamic --timeframe 1d --limit 184
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from backtest.ohlcv_csv_cache import ensure_bars_cached, ohlcv_cache_path
from backtest.run_demo import build_run_demo_parser, resolve_run_demo_symbols
from config.app_settings import load_app_settings


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Fetch OHLCV into CSV cache for backtests.")
    p.add_argument(
        "--cache-dir",
        default=load_app_settings().market.ohlcv_cache_dir,
        help="Output directory (default: config/app.default.json market.ohlcv_cache_dir).",
    )
    p.add_argument(
        "--symbols", default=None, help="Comma-separated pairs (overrides dynamic/default)."
    )
    p.add_argument(
        "--dynamic",
        action="store_true",
        help="Resolve universe like run_demo (config/app.default.json market.universe_symbols).",
    )
    p.add_argument("--ticker", default=load_app_settings().market.default_ticker)
    p.add_argument("--timeframe", default="1d")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--exchange", default="binance")
    p.add_argument("--refresh", action="store_true", help="Overwrite existing CSVs.")
    return p


def main(argv: list[str] | None = None) -> int:
    # Always let `.env` win over inherited shell env (including empty values).
    load_dotenv(override=True)
    args = build_parser().parse_args(argv)
    cache_dir = Path(args.cache_dir).expanduser()
    cache_dir.mkdir(parents=True, exist_ok=True)

    if args.symbols:
        sym_list = [s.strip() for s in args.symbols.split(",") if s.strip()]
        primary = str(args.ticker) if str(args.ticker) in sym_list else sym_list[0]
    elif args.dynamic:
        demo_parser = build_run_demo_parser()
        demo_args = demo_parser.parse_args(
            ["--ticker", str(args.ticker), "--exchange", str(args.exchange), "--steps", "2"]
        )
        sym_list, primary = resolve_run_demo_symbols(demo_args, demo_parser)
        if len(sym_list) < 2:
            print("[prefetch] dynamic universe returned <2 symbols; use --symbols", file=sys.stderr)
            return 1
    else:
        print("[prefetch] pass --symbols LIST or --dynamic", file=sys.stderr)
        return 1

    tf = str(args.timeframe)
    lim = max(2, int(args.limit))
    for sym in sym_list:
        path = ohlcv_cache_path(cache_dir, sym, tf)
        print(f"[prefetch] {sym} {tf} limit={lim} -> {path}", file=sys.stderr)
        ensure_bars_cached(
            sym,
            lim,
            timeframe=tf,
            exchange_id=str(args.exchange),
            cache_dir=cache_dir,
            refresh=bool(args.refresh),
        )
    print(f"[prefetch] done ({len(sym_list)} files under {cache_dir})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
