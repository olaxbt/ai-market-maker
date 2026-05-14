"""Crypto perpetual backtest engine.

Model: USDT-margined linear perpetual contracts.
- 24/7, long/short, no lot-size restrictions
- Initial margin = notional / leverage
- Funding fee settlement every 8h (dedup per slot)
- Tiered maintenance margin liquidation check

Config keys (all plain dict, no env vars):
  leverage=1.0  default leverage
  maker_rate=0.0002
  taker_rate=0.0005
  slippage=0.0005
  funding_rate=0.0001
  initial_cash=10000
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config.runs_paths import runs_dir as _default_runs_dir

_TIER_TABLE = [
    (100_000, 0.004),
    (500_000, 0.006),
    (1_000_000, 0.01),
    (5_000_000, 0.02),
    (10_000_000, 0.05),
    (float("inf"), 0.10),
]

FUNDING_HOURS = {0, 8, 16}


@dataclass
class Position:
    symbol: str
    direction: int
    entry_price: float
    size: float
    leverage: float
    initial_margin: float
    entry_bar_index: int
    entry_commission: float = 0.0


@dataclass
class Trade:
    symbol: str
    direction: int
    entry_price: float
    exit_price: float
    size: float
    leverage: float
    pnl: float
    pnl_pct: float
    exit_reason: str
    holding_bars: int
    commission: float
    #: Bar open time (OHLCV ms or sec) when the trade was closed — for ledgers / UI.
    exit_ts_ms: int = 0
    #: Bar index at exit (0-based) for UI step column.
    exit_bar_index: int = 0


@dataclass
class EquitySnapshot:
    timestamp: int
    capital: float
    unrealized_pnl: float
    equity: float
    position_count: int


class PerpEngine:
    """Perpetual-contract backtest engine.

    Provides a single ``run()`` method that accepts pre-loaded OHLCV bars
    and a signal generator, then steps through bar-by-bar execution.

    All config is passed as a plain dict at construction time — zero env vars.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config or {}
        self.initial_cash: float = float(cfg.get("initial_cash", 10_000))
        self.leverage: float = float(cfg.get("leverage", 1.0))
        self.maker_rate: float = float(cfg.get("maker_rate", 0.0002))
        self.taker_rate: float = float(cfg.get("taker_rate", 0.0005))
        self.slippage_rate: float = float(cfg.get("slippage", 0.0005))
        self.funding_rate: float = float(cfg.get("funding_rate", 0.0001))

        self.capital: float = self.initial_cash
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []
        self.snapshots: list[EquitySnapshot] = []
        self._funding_applied: set[tuple[str, int, int]] = set()
        self._bar_index: int = 0
        self._last_bar_ts: int = 0
        self.interval_sec: int = max(60, int(cfg.get("interval_sec", 300)))

    def can_execute(self, direction: int, bar) -> bool:
        return True

    def round_size(self, raw: float) -> float:
        return round(max(raw, 0.0), 6)

    def calc_commission(self, size: float, price: float, is_open: bool) -> float:
        rate = self.taker_rate if is_open else self.maker_rate
        return size * price * rate

    def apply_slippage(self, price: float, direction: int) -> float:
        return price * (1 + direction * self.slippage_rate)

    @staticmethod
    def maintenance_rate(notional_usd: float) -> float:
        for cap, rate in _TIER_TABLE:
            if notional_usd <= cap:
                return rate
        return _TIER_TABLE[-1][1]

    def on_bar(self, symbol: str, close: float, timestamp_ms: int) -> None:
        self._apply_funding(symbol, close, timestamp_ms)
        self._check_liquidation(symbol, close, timestamp_ms)

    def _apply_funding(self, symbol: str, close: float, ts_ms: int) -> None:
        from datetime import datetime, timezone

        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        slot = (dt.year, dt.month, dt.day, dt.hour)
        hour = dt.hour

        if hour in FUNDING_HOURS:
            dedup_key = (symbol, slot)
            if dedup_key in self._funding_applied:
                return
            self._funding_applied.add(dedup_key)
        else:
            day_key = (symbol, dt.year, dt.month, dt.day)
            if day_key in self._funding_applied:
                return
            self._funding_applied.add(day_key)

        pos = self.positions.get(symbol)
        if pos is None:
            return

        notional = pos.size * close
        fee = notional * self.funding_rate * pos.direction
        self.capital -= fee

    def _check_liquidation(self, symbol: str, close: float, timestamp_ms: int) -> None:
        pos = self.positions.get(symbol)
        if pos is None or pos.leverage <= 1.0:
            return

        margin = pos.initial_margin
        unrealized = pos.direction * pos.size * (close - pos.entry_price)
        notional = pos.size * close
        maint = notional * self.maintenance_rate(notional)

        if (margin + unrealized) <= maint:
            self._close(
                symbol,
                self.apply_slippage(close, -pos.direction),
                "liquidation",
                exit_ts_ms=int(timestamp_ms),
            )

    def run(
        self,
        bars_by_symbol: dict[str, list[list[float]]],
        signal_fn,
        *,
        run_id: str | None = None,
        runs_dir: Path | None = None,
        progress_callback=None,
    ) -> dict[str, Any]:
        symbols = sorted(bars_by_symbol.keys())
        aligned = self._align_bars(bars_by_symbol)
        total_bars = len(aligned.get(symbols[0], []))

        run_id = run_id or f"perp_{int(time.time())}"
        runs_dir = runs_dir or _default_runs_dir()

        for bar_idx in range(total_bars):
            self._bar_index = bar_idx
            window = {s: aligned[s][: bar_idx + 1] for s in symbols}
            last_close = {s: float(aligned[s][bar_idx][4]) for s in symbols}
            last_ts = int(aligned[symbols[0]][bar_idx][0])
            self._last_bar_ts = last_ts

            for sym in symbols:
                self.on_bar(sym, float(last_close[sym]), last_ts)

            for sym in symbols:
                target = signal_fn(
                    sym,
                    window[sym],
                    {k: v for k, v in self.positions.items()},
                    self.capital,
                )
                self._rebalance(
                    sym,
                    float(target),
                    float(aligned[sym][bar_idx][1]),
                    float(last_close[sym]),
                    last_ts,
                    last_close,
                )

            eq = self._equity(last_close)
            snap = EquitySnapshot(
                timestamp=last_ts,
                capital=self.capital,
                unrealized_pnl=eq - self.capital,
                equity=eq,
                position_count=len(self.positions),
            )
            self.snapshots.append(snap)
            if progress_callback is not None:
                try:
                    progress_callback(
                        int(bar_idx),
                        int(total_bars),
                        {
                            "ts": int(last_ts),
                            "equity": float(eq),
                            "capital": float(self.capital),
                            "positions": int(len(self.positions)),
                            "trade_count": int(len(self.trades)),
                        },
                    )
                except Exception:
                    # Progress is best-effort; never break backtests for UI telemetry.
                    pass

        if total_bars > 0:
            final_close = {s: float(aligned[s][-1][4]) for s in symbols}
            final_ts = int(aligned[symbols[0]][-1][0])
            for sym in list(self.positions.keys()):
                self._close(
                    sym,
                    final_close.get(sym, 0.0),
                    "end_of_backtest",
                    exit_ts_ms=final_ts,
                )

        metrics = self._calc_metrics()
        primary_bars = aligned[symbols[0]] if symbols and total_bars > 0 else []
        return self._finalize(run_id, runs_dir, symbols, metrics, primary_bars)

    def _rebalance(
        self,
        symbol: str,
        target_weight: float,
        bar_open: float,
        bar_close: float,
        timestamp_ms: int,
        last_closes: dict[str, float],
    ) -> None:
        target_dir = 1 if target_weight > 1e-9 else (-1 if target_weight < -1e-9 else 0)
        current = self.positions.get(symbol)

        if current is None and target_dir == 0:
            return
        if bar_open <= 1e-12:
            return

        if current is not None:
            if target_dir == 0 or target_dir != current.direction:
                price = self.apply_slippage(bar_open, -current.direction)
                self._close(symbol, price, "signal", exit_ts_ms=int(timestamp_ms))
                current = self.positions.get(symbol)

        if target_dir != 0 and symbol not in self.positions:
            if not self.can_execute(target_dir, None):
                return
            slipped = self.apply_slippage(bar_open, target_dir)
            eq = self._equity(last_closes)
            target_notional = abs(target_weight) * eq * self.leverage
            size = self.round_size(target_notional / slipped)
            if size <= 1e-18:
                return

            margin = size * slipped / self.leverage
            comm = self.calc_commission(size, slipped, is_open=True)

            if margin + comm > self.capital:
                available = max(0.0, self.capital - comm)
                size = self.round_size(available * self.leverage / slipped)
                if size <= 1e-18:
                    return
                margin = size * slipped / self.leverage
                comm = self.calc_commission(size, slipped, is_open=True)

            self.capital -= margin + comm
            self.positions[symbol] = Position(
                symbol=symbol,
                direction=target_dir,
                entry_price=slipped,
                size=size,
                leverage=self.leverage,
                initial_margin=margin,
                entry_bar_index=self._bar_index,
                entry_commission=comm,
            )

    def _close(
        self,
        symbol: str,
        exit_price: float,
        reason: str,
        *,
        exit_ts_ms: int | None = None,
    ) -> None:
        pos = self.positions.pop(symbol, None)
        if pos is None:
            return

        pnl = pos.direction * pos.size * (exit_price - pos.entry_price)
        margin = pos.initial_margin
        pnl_pct = (pnl / margin * 100) if margin > 1e-9 else 0.0
        exit_comm = self.calc_commission(pos.size, exit_price, is_open=False)

        self.capital += margin + pnl - exit_comm
        holding = max(self._bar_index - pos.entry_bar_index, 0)
        ts_exit = int(exit_ts_ms) if exit_ts_ms is not None else int(self._last_bar_ts)

        self.trades.append(
            Trade(
                symbol=pos.symbol,
                direction=pos.direction,
                entry_price=pos.entry_price,
                exit_price=exit_price,
                size=pos.size,
                leverage=pos.leverage,
                pnl=pnl,
                pnl_pct=pnl_pct,
                exit_reason=reason,
                holding_bars=holding,
                commission=pos.entry_commission + exit_comm,
                exit_ts_ms=ts_exit,
                exit_bar_index=int(self._bar_index),
            )
        )

    def _equity(self, last_closes: dict[str, float]) -> float:
        eq = self.capital
        for pos in self.positions.values():
            px = last_closes.get(pos.symbol, pos.entry_price)
            u = pos.direction * pos.size * (px - pos.entry_price)
            eq += pos.initial_margin + u
        return eq

    @staticmethod
    def _align_bars(
        bars_by_symbol: dict[str, list[list[float]]],
    ) -> dict[str, list[list[float]]]:
        import pandas as pd

        aligned = {}
        timestamps: set[int] = set()

        data_frames = {}
        for sym, rows in bars_by_symbol.items():
            df = pd.DataFrame(rows, columns=["ts", "o", "h", "l", "c", "v"])
            df = df.set_index("ts").astype(float)
            data_frames[sym] = df
            timestamps.update(df.index.tolist())

        common = sorted(timestamps)
        for sym, df in data_frames.items():
            reindexed = df.reindex(common).ffill().bfill()
            aligned[sym] = [
                [int(ts), o, hh, lo, c, v]
                for ts, (o, hh, lo, c, v) in zip(
                    common,
                    reindexed[["o", "h", "l", "c", "v"]].itertuples(index=False, name=None),
                    strict=True,
                )
            ]
        return aligned

    def _infer_bar_interval_sec_from_snapshots(self) -> int:
        """Median delta between consecutive bar timestamps (seconds), clamped for sanity.

        OHLCV rows are normally **milliseconds** since epoch (CCXT). Some CSVs or hand-edited
        feeds use **seconds**; treating those as ms makes ``delta/1000`` look like ~86s
        "days" and explodes annualized Sharpe. We detect unit from magnitude and reconcile
        with ``interval_sec`` when inference is an order of magnitude smaller than configured.
        """
        snaps = self.snapshots
        cfg = max(60, int(self.interval_sec))
        if len(snaps) < 2:
            return cfg
        # CCXT-style ms timestamps are ~1e12+ for the 2000s; unix seconds stay below 1e10 for decades.
        ts_sec_unit = abs(int(snaps[-1].timestamp)) < 10_000_000_000
        deltas: list[int] = []
        for i in range(1, len(snaps)):
            raw = int(snaps[i].timestamp) - int(snaps[i - 1].timestamp)
            if ts_sec_unit:
                ds = int(round(raw))
            else:
                ds = int(round(raw / 1000.0))
            if 30 <= ds <= 172_800:
                deltas.append(ds)
        if deltas:
            deltas.sort()
            med = deltas[len(deltas) // 2]
            # If median spacing is far below the engine's configured bar size (e.g. bad unit
            # inference), trust the configured interval for annualization.
            if cfg >= 300 and med > 0 and med < cfg and (cfg / med) >= 4:
                return cfg
            return med
        return cfg

    def _calc_metrics(self) -> dict[str, Any]:
        from backtest.metrics import (
            periods_per_year_from_interval_sec,
            returns_from_equity,
            sharpe_ratio,
        )

        equity_vals = [s.equity for s in self.snapshots] if self.snapshots else [self.initial_cash]
        if not equity_vals:
            return {}

        total_return = (
            (equity_vals[-1] - self.initial_cash) / self.initial_cash * 100
            if self.initial_cash > 0
            else 0.0
        )

        peak = equity_vals[0]
        max_dd = 0.0
        for v in equity_vals:
            peak = max(peak, v)
            dd = (peak - v) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)

        # Annualize from per-bar simple returns. Prefer bar spacing inferred from snapshot
        # timestamps so Sharpe stays correct even if `interval_sec` was not threaded into PerpEngine.
        rets = returns_from_equity(equity_vals)
        bar_sec = self._infer_bar_interval_sec_from_snapshots()
        ppy = periods_per_year_from_interval_sec(bar_sec)
        sharpe = sharpe_ratio(rets, periods_per_year=ppy)

        wins = [t for t in self.trades if t.pnl > 0]
        win_rate = len(wins) / len(self.trades) * 100 if self.trades else 0.0

        return {
            "total_return_pct": round(total_return, 4),
            "max_drawdown_pct": round(max_dd, 4),
            "sharpe": round(sharpe, 4),
            "sharpe_ratio": round(sharpe, 4),
            "sharpe_annualization_bars_per_year": ppy,
            "sharpe_bar_interval_sec_used": bar_sec,
            "win_rate_pct": round(win_rate, 2),
            "total_trades": len(self.trades),
            "total_pnl_usd": round(sum(t.pnl for t in self.trades), 2),
            "total_commission": round(sum(t.commission for t in self.trades), 2),
        }

    def _finalize(
        self,
        run_id: str,
        runs_dir: Path,
        symbols: list[str],
        metrics: dict[str, Any],
        bars_primary: list[list[float]] | None = None,
    ) -> dict[str, Any]:
        import pandas as pd

        out_dir = runs_dir / "backtests" / run_id
        out_dir.mkdir(parents=True, exist_ok=True)

        benchmark: dict[str, Any] = {}
        rows = bars_primary or []
        tr_pct = metrics.get("total_return_pct")
        if len(rows) >= 2 and self.initial_cash > 0:
            from backtest.benchmark import compute_buy_hold_benchmark

            fee_bps = float(self.taker_rate) * 10_000.0
            slip_bps = float(self.slippage_rate) * 10_000.0
            benchmark = dict(
                compute_buy_hold_benchmark(
                    initial_cash_usd=float(self.initial_cash),
                    bars=rows,
                    fee_bps=fee_bps,
                    slippage_bps=slip_bps,
                )
            )
            bh = benchmark.get("benchmark_buy_hold_equity_return_pct")
            if isinstance(bh, (int, float)) and isinstance(tr_pct, (int, float)):
                benchmark["excess_return_vs_buy_hold_equity_pct"] = round(
                    float(tr_pct) - float(bh), 6
                )

        eq_records = []
        for s in self.snapshots:
            eq_records.append(
                {
                    "ts": s.timestamp,
                    "capital": round(s.capital, 8),
                    "unrealized_pnl": round(s.unrealized_pnl, 8),
                    "equity": round(s.equity, 8),
                    "positions": s.position_count,
                }
            )
        pd.DataFrame(eq_records).to_json(out_dir / "equity.jsonl", orient="records", lines=True)

        trade_records = []
        for t in self.trades:
            rec: dict[str, Any] = {
                "symbol": t.symbol,
                "direction": t.direction,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "size": t.size,
                "leverage": t.leverage,
                "pnl": round(t.pnl, 8),
                "pnl_pct": round(t.pnl_pct, 4),
                "exit_reason": t.exit_reason,
                "holding_bars": t.holding_bars,
                "commission": round(t.commission, 8),
                "exit_bar_index": int(t.exit_bar_index),
            }
            if int(t.exit_ts_ms) > 0:
                # Binance ``myTrades``-style epoch ms — ``normalize_trade_row_for_api`` maps to ``ts_ms`` for web UI.
                rec["time"] = int(t.exit_ts_ms)
                rec["exit_ts_ms"] = int(t.exit_ts_ms)
            trade_records.append(rec)
        pd.DataFrame(trade_records).to_json(out_dir / "trades.jsonl", orient="records", lines=True)

        start_ts = int(self.snapshots[0].timestamp) if self.snapshots else None
        end_ts = int(self.snapshots[-1].timestamp) if self.snapshots else None
        start_iso = None
        end_iso = None
        if start_ts is not None and end_ts is not None:
            try:
                from datetime import datetime, timezone

                start_iso = datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc).isoformat()
                end_iso = datetime.fromtimestamp(end_ts / 1000, tz=timezone.utc).isoformat()
            except Exception:
                start_iso = None
                end_iso = None

        summary = {
            "run_id": run_id,
            "instrument": "perp",
            "leverage": self.leverage,
            "initial_cash": self.initial_cash,
            "final_equity": round(self.snapshots[-1].equity, 2)
            if self.snapshots
            else self.initial_cash,
            "metrics": metrics,
            "benchmark": benchmark,
            "symbols": symbols,
            "interval_sec": self.interval_sec,
            "bar_interval_sec_inferred": self._infer_bar_interval_sec_from_snapshots(),
            "equity_convention": (
                "USDT-margined linear perpetual model: equity = free_collateral + Σ(locked_initial_margin "
                "+ unrealized_pnl) per open position. Not spot wallet balances; exposure is via contract PnL."
            ),
            "total_bars": len(self.snapshots),
            "start_ts": start_ts,
            "end_ts": end_ts,
            "start_iso": start_iso,
            "end_iso": end_iso,
        }
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))

        return summary
