"""Prefetch OHLCV cache for the README default backtest.

Examples::

    uv run python -m backtest.bootstrap_showcase
    uv run python -m backtest.bootstrap_showcase --eval-steps 180

Then run offline from cache::

    uv run python -m backtest.run_demo \\
      --symbols 'BTC/USDT,ETH/USDT,SOL/USDT' \\
      --steps 180 --csv-only --timeframe 1d --ticker BTC/USDT
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from backtest.ohlcv_csv_cache import ensure_bars_cached, ohlcv_cache_path
from backtest.ta_warmup import total_fetch_bars
from config.app_settings import load_app_settings


def build_parser() -> argparse.ArgumentParser:
    app = load_app_settings()
    p = argparse.ArgumentParser(
        description="Prefetch OHLCV for the default backtest (warmup + eval bars)."
    )
    p.add_argument(
        "--symbols",
        default=",".join(app.market.universe_symbols or ["BTC/USDT", "ETH/USDT", "SOL/USDT"]),
        help="Comma-separated pairs (default: market.universe_symbols).",
    )
    p.add_argument("--eval-steps", type=int, default=180, help="Evaluation bars (default: 180).")
    p.add_argument(
        "--no-warmup",
        action="store_true",
        help="Prefetch eval bars only (skip TA warmup prefix).",
    )
    p.add_argument("--timeframe", default="1d")
    p.add_argument("--exchange", default="binance")
    p.add_argument(
        "--cache-dir",
        default=app.market.ohlcv_cache_dir,
        help="OHLCV CSV directory (default: market.ohlcv_cache_dir).",
    )
    p.add_argument("--refresh", action="store_true", help="Overwrite existing CSVs.")
    return p


def main(argv: list[str] | None = None) -> int:
    load_dotenv(override=True)
    args = build_parser().parse_args(argv)
    cache_dir = Path(args.cache_dir).expanduser()
    cache_dir.mkdir(parents=True, exist_ok=True)

    symbols = [s.strip() for s in str(args.symbols).split(",") if s.strip()]
    if len(symbols) < 1:
        print("[bootstrap] need at least one symbol", file=sys.stderr)
        return 1

    fetch_limit, warmup = (
        (int(args.eval_steps), 0)
        if bool(args.no_warmup)
        else total_fetch_bars(eval_steps=int(args.eval_steps))
    )
    tf = str(args.timeframe)
    if warmup > 0:
        print(
            f"[bootstrap] prefetch {fetch_limit} x {tf} bars "
            f"({warmup} warmup + {int(args.eval_steps)} eval) for {len(symbols)} symbols",
            file=sys.stderr,
        )
    else:
        print(
            f"[bootstrap] prefetch {fetch_limit} eval x {tf} bars for {len(symbols)} symbols (no warmup)",
            file=sys.stderr,
        )
    for sym in symbols:
        path = ohlcv_cache_path(cache_dir, sym, tf)
        print(f"  {sym} -> {path}", file=sys.stderr)
        ensure_bars_cached(
            sym,
            fetch_limit,
            timeframe=tf,
            exchange_id=str(args.exchange),
            cache_dir=cache_dir,
            refresh=bool(args.refresh),
        )

    sym_arg = ",".join(symbols)
    print(
        "\n[bootstrap] done. Run default backtest (offline after first prefetch):\n"
        f"  uv run python -m backtest.run_demo \\\n"
        f"    --symbols '{sym_arg}' --steps {int(args.eval_steps)} \\\n"
        f"    --csv-only --timeframe {tf} --ticker {symbols[0]}\n",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
