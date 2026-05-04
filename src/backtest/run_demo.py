"""Multi-step backtest CLI: **online** exchange candles (public fetch) or cached CSV (offline).

**CSV cache:** ``--ohlcv-cache-dir DIR`` (or ``config/app.default.json`` ``market.ohlcv_cache_dir``) stores one ``.csv`` per
symbol/timeframe; combine with ``--online`` to fill on first run and reuse later. ``--csv-only``
runs fully offline from that folder (populate via ``python -m backtest.prefetch_ohlcv``).

Online (Binance public ``fetch_ohlcv``, no API keys)::

    uv run python -m backtest.run_demo --online --steps 90 --timeframe 1d

Multi-symbol (aligned OHLCV; same portfolio path as production graph). If you omit ``--symbols``:

- **Static (default):** uses ``config/app.default.json`` ``market.universe_symbols`` (capped by ``market.universe_size``).

Examples::

    NEXUS_DISABLE=1 AI_MARKET_MAKER_USE_LLM=0 uv run python -m backtest.run_demo --steps 80 --online --timeframe 1d

~6 months daily, dynamic top-liquid universe, frequent-style env (no ``--symbols``)::

    NEXUS_DISABLE=1 uv run python -m backtest.run_demo --online --timeframe 1d --steps 184

Single-symbol (legacy)::

    uv run python -m backtest.run_demo --ticker-only --steps 40 --online --timeframe 1d

Long horizon (monthly candles ≈ years of history; fewer LLM calls than daily)::

    uv run python -m backtest.run_demo --online --timeframe 1M --steps 36 --llm

Expand history until at least one simulated fill (cap ``--max-fetch``)::

    uv run python -m backtest.run_demo --online --min-trades 1 --steps 40 --max-fetch 200

Use Tier-2 LLM arbitrator (one LLM call per bar; set API keys in ``.env``).
Steps are capped by ``AIMM_BACKTEST_LLM_MAX_STEPS`` (default **120**) unless you raise it::

    uv run python -m backtest.run_demo --llm --steps 15
    AIMM_BACKTEST_LLM_MAX_STEPS=200 uv run python -m backtest.run_demo --online --timeframe 1d --steps 180 --llm

Frequent-trading **style** (more signals / sizing from aggressive + active + rule floors) works on **daily**
bars too — you get one graph step per day but **more symbols** and **longer calendars** for trade count.
Optional LLM: raise ``AIMM_BACKTEST_LLM_MAX_STEPS`` to at least ``--steps`` or the run is truncated.

Hourly (shorter calendar, more steps per week)::

    NEXUS_DISABLE=1 AIMM_STRATEGY_PRESET=aggressive AIMM_TRADING_STYLE=active \\
      AIMM_BACKTEST_LLM_MAX_STEPS=60 AIMM_RULE_SENTIMENT_BUY_MIN=45 \\
      uv run python -m backtest.run_demo --llm --online --timeframe 1h --steps 60 --ticker BTC/USDT

Daily ~half-year + dynamic universe + LLM (expensive: ~184 LLM calls)::

    NEXUS_DISABLE=1 AIMM_BACKTEST_LLM_MAX_STEPS=200 \\
      uv run python -m backtest.run_demo --llm --online --timeframe 1d --steps 184 --ticker BTC/USDT

Each bar appends one row to ``.runs/backtests/<run_id>/iterations.jsonl`` (stance, trade_intent,
execution stub, ``llm_arbitrator`` flag) — similar in spirit to a per-cycle AI report.

**Multi-year / anchored windows** (fixed calendar ranges + aggregate JSON/Markdown report)::

    NEXUS_DISABLE=1 uv run python -m backtest.run_historical_eval --suite daily
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from backtest.bars import (
    align_bars_by_min_length,
    fetch_ccxt_ohlcv_bars,
    interval_sec_to_ccxt_timeframe,
    nominal_interval_sec_for_timeframe,
)
from backtest.loop import run_multi_step_backtest
from backtest.ohlcv_csv_cache import ensure_bars_cached, load_bars_csv_only
from config.app_settings import load_app_settings

try:
    from config.leaderboard_submit import load_leaderboard_submit_config
    from leaderboard_submitter import submit_backtest_result
except ImportError:  # optional in some stripped-down builds
    load_leaderboard_submit_config = None  # type: ignore[assignment]
    submit_backtest_result = None  # type: ignore[assignment]


def _infer_interval_sec_from_bars(bars: list[list[float]]) -> int:
    if len(bars) < 2:
        return 86_400
    dt_ms = float(bars[1][0] - bars[0][0])
    return max(60, int(dt_ms / 1000.0))


def build_run_demo_parser() -> argparse.ArgumentParser:
    _def_ticker = load_app_settings().market.default_ticker
    parser = argparse.ArgumentParser(
        description="Multi-step backtest (real OHLCV via exchange or cached CSV)."
    )
    parser.add_argument(
        "--ticker",
        default=_def_ticker,
        help="Primary pair (default: config/app.default.json market.default_ticker).",
    )
    parser.add_argument(
        "--symbols",
        default=None,
        metavar="LIST",
        help=(
            "Multi-asset: comma-separated pairs. If omitted, uses AIMM_UNIVERSE or built-in defaults "
            "(BTC, ETH, SOL, AIO/USDT, … up to AIMM_UNIVERSE_SIZE). Use --ticker-only for single-asset."
        ),
    )
    parser.add_argument(
        "--ticker-only",
        action="store_true",
        help="Run single-symbol path with only --ticker (skip default multi-universe).",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=20,
        help="Candles to fetch (then may expand).",
    )
    parser.add_argument(
        "--interval-sec",
        type=int,
        default=86_400,
        help="Selects default CCXT timeframe when --online and no --timeframe.",
    )
    parser.add_argument(
        "--online", action="store_true", help="Fetch OHLCV from exchange (public data)."
    )
    parser.add_argument(
        "--exchange",
        default="binance",
        help="CCXT exchange id (default: binance).",
    )
    parser.add_argument(
        "--timeframe",
        default=None,
        help="Override CCXT timeframe e.g. 1h, 4h, 1d, 1w, 1M (default: derived from --interval-sec).",
    )
    parser.add_argument("--initial-cash", type=float, default=10_000.0)
    parser.add_argument(
        "--instrument",
        default=None,
        choices=("spot", "perp"),
        help="Backtest book: spot (pay full notional) or perp (USDT margin = notional/leverage). Default: config paper.instrument.",
    )
    parser.add_argument(
        "--leverage",
        type=float,
        default=None,
        help="Perp leverage for mock margin (default: config paper.leverage).",
    )
    parser.add_argument(
        "--deploy-spot-pct",
        type=float,
        default=0.0,
        help=(
            "Single-symbol only: put this %% of --initial-cash into spot at bar 0 (rest stays cash). "
            "Makes buy-and-hold benchmark compare to the same starting equity (cash + coin). "
            "Use e.g. 100 for apples-to-apples tactical alpha vs full passivity."
        ),
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--min-trades",
        type=int,
        default=0,
        help="If >0 with --online, refetch with larger history until trade_count >= min-trades or --max-fetch.",
    )
    parser.add_argument(
        "--max-fetch",
        type=int,
        default=300,
        help="Max candles to pull when expanding for --min-trades (exchange limits vary).",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Set AI_MARKET_MAKER_USE_LLM=1 before the run (LLM per bar; requires provider keys).",
    )
    parser.add_argument(
        "--runs-dir",
        default=None,
        metavar="DIR",
        help="Write ``.runs/`` tree under this directory instead of the process cwd (tests, sandboxes).",
    )
    parser.add_argument(
        "--ohlcv-cache-dir",
        default=None,
        metavar="DIR",
        help=(
            "Read/write OHLCV CSVs under DIR (one file per symbol/timeframe). "
            "With --online: fill cache on miss. Env default: AIMM_OHLCV_CACHE_DIR."
        ),
    )
    parser.add_argument(
        "--refresh-ohlcv-cache",
        action="store_true",
        help="With --online and cache dir: refetch and overwrite CSVs.",
    )
    parser.add_argument(
        "--csv-only",
        action="store_true",
        help="Load bars from cache dir only (no network). Requires CSVs from prefetch_ohlcv.",
    )
    return parser


def resolve_run_demo_symbols(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> tuple[list[str], str]:
    """Return ``(sym_list, primary)``. Empty ``sym_list`` selects single-asset mode."""
    if args.ticker_only:
        return [], str(args.ticker)
    sym_list = [s.strip() for s in (args.symbols or "").split(",") if s.strip()]
    if not sym_list:
        s = load_app_settings()
        u_sz = max(2, int(s.market.universe_size))
        pool = list(s.market.universe_symbols)
        sym_list = [str(args.ticker)] + [x for x in pool if x != str(args.ticker)]
        sym_list = sym_list[:u_sz]
    # Optional: drop stablecoin legs for clearer "risk assets" comparisons.
    # Stable exclusion removed in frozen config mode (explicit universe list should be curated).
    if False and sym_list:

        def _is_stable(sym: str) -> bool:
            s = (sym or "").upper()
            return any(
                x in s for x in ("USDC/USDT", "USD1/USDT", "FDUSD/USDT", "TUSD/USDT", "USDP/USDT")
            )

        before = list(sym_list)
        sym_list = [s for s in sym_list if not _is_stable(s)]
        # Keep at least the primary ticker.
        if not sym_list:
            sym_list = [str(args.ticker)]
        if before != sym_list:
            print(f"[universe] excluded stables → {sym_list}", file=sys.stderr)
    if sym_list:
        if len(sym_list) < 2:
            parser.error("--symbols requires at least two pairs (comma-separated)")
        if int(args.min_trades) > 0:
            print(
                "[run_demo] ignoring --min-trades for multi-symbol run",
                file=sys.stderr,
            )
        if float(args.deploy_spot_pct) > 0:
            print(
                "[run_demo] ignoring --deploy-spot-pct for multi-symbol run",
                file=sys.stderr,
            )
        primary = str(args.ticker) if str(args.ticker) in sym_list else sym_list[0]
        return sym_list, primary
    return [], str(args.ticker)


def execute_run_demo(args: argparse.Namespace, parser: argparse.ArgumentParser) -> dict[str, Any]:
    sym_list, primary = resolve_run_demo_symbols(args, parser)
    runs_dir_path = Path(args.runs_dir).expanduser() if args.runs_dir else None

    raw_cache = (
        getattr(args, "ohlcv_cache_dir", None) or load_app_settings().market.ohlcv_cache_dir or ""
    ).strip()
    ohlcv_cache: Path | None = Path(raw_cache).expanduser() if raw_cache else None
    if bool(getattr(args, "csv_only", False)) and not ohlcv_cache:
        parser.error("--csv-only requires --ohlcv-cache-dir (or set market.ohlcv_cache_dir)")
    if bool(getattr(args, "csv_only", False)) and bool(args.online):
        print("[run_demo] --csv-only: using cached CSVs only (no exchange fetch).", file=sys.stderr)

    tf = args.timeframe or interval_sec_to_ccxt_timeframe(args.interval_sec)
    limit = max(2, int(args.steps))
    llm_cap: int | None = None
    if args.llm:
        cap_raw = (os.getenv("AIMM_BACKTEST_LLM_MAX_STEPS") or "120").strip()
        try:
            llm_cap = max(2, int(cap_raw, 10))
        except ValueError:
            llm_cap = 120
        if limit > llm_cap:
            print(
                f"[llm] capping --steps {limit} → {llm_cap} (AIMM_BACKTEST_LLM_MAX_STEPS); "
                "raise env for longer production-style runs.",
                file=sys.stderr,
            )
            limit = llm_cap
    max_fetch = max(limit, int(args.max_fetch))
    if args.llm and llm_cap is not None:
        max_fetch = min(max_fetch, llm_cap)

    bars: list[list[float]] = []
    res = None
    attempt = 0

    if sym_list:
        limit_m = max(2, int(args.steps))
        if args.llm and llm_cap is not None:
            limit_m = min(limit_m, llm_cap)
        bars_map: dict[str, list[list[float]]] = {}
        refresh_csv = bool(getattr(args, "refresh_ohlcv_cache", False))
        csv_only = bool(getattr(args, "csv_only", False))
        for _idx, sym in enumerate(sym_list):
            if csv_only:
                assert ohlcv_cache is not None
                print(f"[csv] loading {limit_m} x {tf} {sym} from {ohlcv_cache} …", file=sys.stderr)
                bars_map[sym] = load_bars_csv_only(
                    sym, limit_m, timeframe=tf, cache_dir=ohlcv_cache
                )
            elif args.online:
                if ohlcv_cache is not None:
                    print(
                        f"[cache] ensure {limit_m} x {tf} {sym} under {ohlcv_cache} …",
                        file=sys.stderr,
                    )
                    bars_map[sym] = ensure_bars_cached(
                        sym,
                        limit_m,
                        timeframe=tf,
                        exchange_id=str(args.exchange),
                        cache_dir=ohlcv_cache,
                        refresh=refresh_csv,
                    )
                else:
                    print(
                        f"[online] fetching {limit_m} x {tf} {sym} from {args.exchange} …",
                        file=sys.stderr,
                    )
                    bars_map[sym] = fetch_ccxt_ohlcv_bars(
                        sym,
                        limit_m,
                        timeframe=tf,
                        exchange_id=args.exchange,
                    )
            elif args.flat:
                raise ValueError(
                    "--flat is no longer supported (synthetic bars removed). Use --online or --csv-only."
                )
            else:
                raise ValueError("synthetic bars removed. Use --online or --csv-only.")
        aligned = align_bars_by_min_length(bars_map)
        interval_m = _infer_interval_sec_from_bars(aligned[primary])
        if (args.online or csv_only) and args.timeframe:
            interval_m = max(interval_m, nominal_interval_sec_for_timeframe(args.timeframe))
        res = run_multi_step_backtest(
            ticker=primary,
            bars_by_symbol=aligned,
            initial_cash=args.initial_cash,
            interval_sec=interval_m,
            run_id=args.run_id,
            runs_dir=runs_dir_path,
            instrument=args.instrument,
            leverage=args.leverage,
        )

    while not sym_list:
        attempt += 1
        _csv_only = bool(getattr(args, "csv_only", False))
        _refresh = bool(getattr(args, "refresh_ohlcv_cache", False))
        if _csv_only:
            assert ohlcv_cache is not None
            print(f"[csv] loading {limit} x {tf} {args.ticker} …", file=sys.stderr)
            bars = load_bars_csv_only(str(args.ticker), limit, timeframe=tf, cache_dir=ohlcv_cache)
            interval_sec = _infer_interval_sec_from_bars(bars)
        elif args.online:
            if ohlcv_cache is not None:
                print(f"[cache] ensure {limit} x {tf} {args.ticker} …", file=sys.stderr)
                bars = ensure_bars_cached(
                    str(args.ticker),
                    limit,
                    timeframe=tf,
                    exchange_id=str(args.exchange),
                    cache_dir=ohlcv_cache,
                    refresh=_refresh,
                )
            else:
                print(
                    f"[online] fetching {limit} x {tf} {args.ticker} from {args.exchange} …",
                    file=sys.stderr,
                )
                bars = fetch_ccxt_ohlcv_bars(
                    args.ticker,
                    limit,
                    timeframe=tf,
                    exchange_id=args.exchange,
                )
            interval_sec = _infer_interval_sec_from_bars(bars)
        elif args.flat:
            raise ValueError(
                "--flat is no longer supported (synthetic bars removed). Use --online or --csv-only."
            )
        else:
            raise ValueError("synthetic bars removed. Use --online or --csv-only.")
        # When --online, bar timestamps define spacing; optional explicit tf aligns synthetic-like labeling.
        if (args.online or _csv_only) and args.timeframe:
            interval_sec = max(interval_sec, nominal_interval_sec_for_timeframe(args.timeframe))

        deploy_pct = max(0.0, min(100.0, float(args.deploy_spot_pct)))
        ic = float(args.initial_cash)
        ibtc = 0.0
        if deploy_pct > 0 and bars:
            p0 = float(bars[0][4])
            if p0 > 0:
                usd_in_asset = ic * (deploy_pct / 100.0)
                ibtc = usd_in_asset / p0
                ic = max(0.0, ic - usd_in_asset)

        res = run_multi_step_backtest(
            ticker=args.ticker,
            bars=bars,
            initial_cash=ic,
            initial_btc=ibtc,
            interval_sec=interval_sec,
            run_id=args.run_id
            if attempt == 1
            else f"{args.run_id or 'bt'}_e{attempt}_{int(time.time())}",
            runs_dir=runs_dir_path,
            instrument=args.instrument,
            leverage=args.leverage,
        )

        need = int(args.min_trades)
        if not args.online or need <= 0 or res.trade_count >= need:
            break
        if limit >= max_fetch:
            print(
                f"[online] stopped at max-fetch={max_fetch} with trade_count={res.trade_count} (need {need})",
                file=sys.stderr,
            )
            break
        step = max(20, min(60, limit // 2))
        limit = min(max_fetch, limit + step)
        if llm_cap is not None:
            limit = min(limit, llm_cap)
        print(
            f"[online] trade_count={res.trade_count} < {need}; expanding to {limit} candles …",
            file=sys.stderr,
        )

    assert res is not None
    bench_d = dict(res.benchmark) if res.benchmark is not None else {}
    initial_eq = float(bench_d.get("benchmark_initial_equity_usd") or args.initial_cash)
    final = float(res.final_equity) if res.final_equity is not None else initial_eq
    pnl_pct = ((final - initial_eq) / initial_eq * 100.0) if initial_eq else 0.0

    _used_exchange_data = bool(args.online) or bool(getattr(args, "csv_only", False))
    out = {
        "run_id": res.run_id,
        "steps": res.steps,
        "trade_count": res.trade_count,
        "llm": bool(args.llm),
        "interval_sec": res.interval_sec,
        "online": bool(args.online),
        "csv_only": bool(getattr(args, "csv_only", False)),
        "ohlcv_cache_dir": str(ohlcv_cache.resolve()) if ohlcv_cache else None,
        "timeframe": tf if _used_exchange_data else None,
        "metrics": res.metrics,
        "benchmark": bench_d,
        "initial_cash_usd": float(args.initial_cash),
        "initial_equity_usd": round(initial_eq, 2),
        "deploy_spot_pct": max(0.0, min(100.0, float(args.deploy_spot_pct))),
        "final_equity_usd": round(final, 2),
        "total_return_pct": round(pnl_pct, 4),
        "summary_path": str(res.summary_path),
        "trades_path": str(res.trades_path),
        "equity_path": str(res.equity_path),
        "iterations_path": str(res.iterations_path) if res.iterations_path else None,
        "events_path": str(res.events_path),
    }
    if sym_list:
        out["multi_asset"] = True
        out["universe"] = list(sym_list)

    # ── Auto-submit to leaderboard if enabled ──
    try:
        if load_leaderboard_submit_config is None or submit_backtest_result is None:
            raise ImportError("leaderboard submitter not available")

        lb_cfg = load_leaderboard_submit_config()
        if lb_cfg.enabled and lb_cfg.submit_backtests:
            summary = {
                "total_return_pct": out.get("total_return_pct"),
                "total_return_vs_hold_pct": (
                    (out.get("total_return_pct") or 0)
                    - (out.get("benchmark", {}).get("total_return_pct") or 0)
                    if isinstance(out.get("benchmark"), dict)
                    else None
                ),
                "sharpe_ratio": out.get("metrics", {}).get("sharpe")
                if isinstance(out.get("metrics"), dict)
                else None,
                "max_drawdown_pct": out.get("metrics", {}).get("max_drawdown_pct")
                if isinstance(out.get("metrics"), dict)
                else out.get("metrics", {}).get("max_drawdown"),
                "win_rate_pct": out.get("metrics", {}).get("win_rate_pct")
                if isinstance(out.get("metrics"), dict)
                else None,
                "total_trades": out.get("metrics", {}).get("n_trades")
                if isinstance(out.get("metrics"), dict)
                else None,
                "initial_capital_usd": out.get("initial_cash_usd"),
                "final_value_usd": out.get("final_equity_usd"),
            }
            ticker = (args.ticker or "").strip() if hasattr(args, "ticker") else ""
            if not ticker and hasattr(args, "ticker_list") and args.ticker_list:
                ticker = args.ticker_list[0] if isinstance(args.ticker_list, list) else ""
            submit_backtest_result(ticker=ticker or "multi-asset", summary=summary, config=lb_cfg)
    except ImportError:
        pass  # leaderboard submitter not available
    except Exception:
        pass

    return out


def main(argv: list[str] | None = None) -> dict[str, Any]:
    load_dotenv()
    parser = build_run_demo_parser()
    args = parser.parse_args(argv)
    if args.llm:
        # Backtest LLM is intentionally **arbitrator-only** by default.
        # Rationale: full-graph LLM calls are too slow/costly per-bar for a demo backtest.
        os.environ["AI_MARKET_MAKER_USE_LLM"] = "1"  # enables LLM signal arbitrator
        os.environ["AIMM_LLM_MODE"] = "0"  # disable portfolio LLM nodes
        os.environ["AIMM_LLM_DESK_DEBATE"] = "0"  # disable extra LLM debate turns
    out = execute_run_demo(args, parser)
    print(json.dumps(out, indent=2), flush=True)
    return out


if __name__ == "__main__":
    main()
