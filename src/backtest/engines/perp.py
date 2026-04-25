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
        self._check_liquidation(symbol, close)

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

    def _check_liquidation(self, symbol: str, close: float) -> None:
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
            )

    def run(
        self,
        bars_by_symbol: dict[str, list[list[float]]],
        signal_fn,
        *,
        run_id: str | None = None,
        runs_dir: Path | None = None,
    ) -> dict[str, Any]:

        symbols = sorted(bars_by_symbol.keys())
        aligned = self._align_bars(bars_by_symbol)
        total_bars = len(aligned.get(symbols[0], []))

        run_id = run_id or f"perp_{int(time.time())}"
        runs_dir = runs_dir or Path(".runs")

        for bar_idx in range(total_bars):
            self._bar_index = bar_idx
            window = {s: aligned[s][: bar_idx + 1] for s in symbols}
            last_close = {s: float(aligned[s][bar_idx][4]) for s in symbols}
            last_ts = int(aligned[symbols[0]][bar_idx][0])

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

        if total_bars > 0:
            final_close = {s: float(aligned[s][-1][4]) for s in symbols}
            for sym in list(self.positions.keys()):
                self._close(sym, final_close.get(sym, 0.0), "end_of_backtest")

        metrics = self._calc_metrics()
        return self._finalize(run_id, runs_dir, symbols, metrics)

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
                self._close(symbol, price, "signal")
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

    def _close(self, symbol: str, exit_price: float, reason: str) -> None:
        pos = self.positions.pop(symbol, None)
        if pos is None:
            return

        pnl = pos.direction * pos.size * (exit_price - pos.entry_price)
        margin = pos.initial_margin
        pnl_pct = (pnl / margin * 100) if margin > 1e-9 else 0.0
        exit_comm = self.calc_commission(pos.size, exit_price, is_open=False)

        self.capital += margin + pnl - exit_comm
        holding = max(self._bar_index - pos.entry_bar_index, 0)

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

    def _calc_metrics(self) -> dict[str, Any]:
        import math

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

        returns = [
            (equity_vals[i] - equity_vals[i - 1]) / equity_vals[i - 1]
            for i in range(1, len(equity_vals))
            if equity_vals[i - 1] > 0
        ]
        avg_ret = sum(returns) / len(returns) if returns else 0.0
        std = math.sqrt(sum((r - avg_ret) ** 2 for r in returns) / max(len(returns), 1))
        sharpe = (avg_ret / std * math.sqrt(365 * 24 * 60 * 60)) if std > 0 else 0.0

        wins = [t for t in self.trades if t.pnl > 0]
        win_rate = len(wins) / len(self.trades) * 100 if self.trades else 0.0

        return {
            "total_return_pct": round(total_return, 4),
            "max_drawdown_pct": round(max_dd, 4),
            "sharpe_ratio": round(sharpe, 4),
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
    ) -> dict[str, Any]:
        import pandas as pd

        out_dir = runs_dir / "backtests" / run_id
        out_dir.mkdir(parents=True, exist_ok=True)

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
            trade_records.append(
                {
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
                }
            )
        pd.DataFrame(trade_records).to_json(out_dir / "trades.jsonl", orient="records", lines=True)

        summary = {
            "run_id": run_id,
            "instrument": "perp",
            "leverage": self.leverage,
            "initial_cash": self.initial_cash,
            "final_equity": round(self.snapshots[-1].equity, 2)
            if self.snapshots
            else self.initial_cash,
            "metrics": metrics,
            "symbols": symbols,
            "total_bars": len(self.snapshots),
        }
        (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))

        return summary
