"""Backtest engine that drives the LangGraph workflow over OHLCV bars."""

from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List

from config.fund_policy import FundPolicy, load_fund_policy
from config.run_mode import RunMode
from flow_log import FlowEventRepo, set_flow_repo
from main import build_workflow
from paper_account import PaperAccount, PerpPosition, apply_perp_fill
from schemas.state import initial_hedge_fund_state

from .bars import align_bars_by_min_length
from .benchmark import compute_buy_hold_benchmark, compute_equal_weight_buy_hold_benchmark
from .exchange_trade_format import build_binance_my_trades_row, quote_asset_from_ccxt, trades_to_csv
from .export_run import export_run_bundle
from .metrics import compute_basic_metrics
from .trade_book import write_jsonl_records


def _compact_proposed_for_iteration(sig: Any) -> dict[str, Any]:
    """Small snapshot for per-bar decision ledger (backtest iterations)."""
    if not isinstance(sig, dict):
        return {}
    meta = sig.get("meta") if isinstance(sig.get("meta"), dict) else {}
    params = sig.get("params")
    out: dict[str, Any] = {
        "action": sig.get("action"),
        "source": meta.get("source"),
        "model": meta.get("model"),
    }
    if isinstance(params, dict):
        out["stance"] = params.get("stance")
        out["confidence"] = params.get("confidence")
        rs = params.get("reasons")
        if isinstance(rs, list):
            out["reasons"] = [str(x) for x in rs[:12]]
        te = params.get("tool_events")
        if isinstance(te, list):
            out["tool_events_count"] = len(te)
        if "llm_json_parse_ok" in params:
            out["llm_json_parse_ok"] = params.get("llm_json_parse_ok")
        if "llm_vs_reference_stance_match" in params:
            out["llm_vs_reference_stance_match"] = params.get("llm_vs_reference_stance_match")
        if params.get("llm_reference_stance") is not None:
            out["llm_reference_stance"] = params.get("llm_reference_stance")
    return out


def _compact_smart_order(so: Any) -> dict[str, Any]:
    if not isinstance(so, dict):
        return {}
    return {
        "status": so.get("status"),
        "side": so.get("side"),
        "qty": so.get("qty"),
    }


def _compact_debate_for_iteration(output: Dict[str, Any]) -> list[dict[str, Any]]:
    dt = output.get("debate_transcript")
    if not isinstance(dt, list):
        return []
    out: list[dict[str, Any]] = []
    for row in dt[-6:]:
        if not isinstance(row, dict):
            continue
        t = str(row.get("text") or "")
        if len(t) > 280:
            t = t[:280] + "…"
        out.append(
            {
                "speaker": row.get("speaker"),
                "role": row.get("role"),
                "text": t,
                "tools_used": row.get("tools_used"),
            }
        )
    return out


def _llm_arbitrator_used(output: Dict[str, Any]) -> bool:
    """``portfolio_proposal`` overwrites ``proposed_signal``; recover LLM from upstream or logs."""
    ps = output.get("proposed_signal")
    if isinstance(ps, dict):
        meta = ps.get("meta")
        if isinstance(meta, dict):
            upstream = meta.get("upstream_signal")
            if isinstance(upstream, dict):
                um = upstream.get("meta")
                if isinstance(um, dict) and um.get("source") == "signal_arbitrator_llm":
                    return True
    for row in output.get("reasoning_logs") or []:
        if not isinstance(row, dict):
            continue
        ex = row.get("extra")
        if (
            isinstance(ex, dict)
            and row.get("node") == "signal_arbitrator"
            and ex.get("llm") is True
        ):
            return True
    return False


def _compact_signal_arbitrator_upstream(output: Dict[str, Any]) -> Dict[str, Any]:
    ps = output.get("proposed_signal")
    if not isinstance(ps, dict):
        return {}
    meta = ps.get("meta")
    if not isinstance(meta, dict):
        return {}
    upstream = meta.get("upstream_signal")
    if not isinstance(upstream, dict):
        return {}
    um = upstream.get("meta") if isinstance(upstream.get("meta"), dict) else {}
    params = upstream.get("params")
    out: Dict[str, Any] = {"source": um.get("source"), "model": um.get("model")}
    if isinstance(params, dict):
        out["stance"] = params.get("stance")
        out["confidence"] = params.get("confidence")
        rs = params.get("reasons")
        if isinstance(rs, list):
            out["reasons"] = [str(x) for x in rs[:12]]
        te = params.get("tool_events")
        if isinstance(te, list):
            out["tool_events_count"] = len(te)
        if "llm_json_parse_ok" in params:
            out["llm_json_parse_ok"] = params.get("llm_json_parse_ok")
        if "llm_vs_reference_stance_match" in params:
            out["llm_vs_reference_stance_match"] = params.get("llm_vs_reference_stance_match")
        if params.get("llm_reference_stance") is not None:
            out["llm_reference_stance"] = params.get("llm_reference_stance")
        if params.get("llm_reference_kind") is not None:
            out["llm_reference_kind"] = params.get("llm_reference_kind")
    return out


@dataclass
class BacktestConfig:
    initial_cash_usd: float = 10000.0
    initial_btc: float = 0.0
    fee_bps: float = 10.0  # 0.10%
    slippage_bps: float = 5.0  # realistic slippage
    interval_sec: int = 300
    max_steps: int | None = None
    progress_callback: Callable[[int, int, dict], None] | None = None
    runs_dir: Path | None = None
    export_bundle: bool = True
    #: Minimum number of bars between trade fills (per-symbol). Helps prevent churn on noisy timeframes.
    min_bars_between_trades: int = 0
    #: ``spot`` = pay full notional; ``perp`` = USDT-margined linear (initial margin = notional / leverage).
    instrument: str = "spot"
    #: Default leverage for perp fills (clamped by :class:`FundPolicy.max_leverage`).
    leverage: float = 3.0


@dataclass
class BacktestSimState:
    cash_usd: float
    btc: float
    #: Volume-weighted average entry for the open long (0 if flat); used for stop-loss binds.
    entry_avg_price: float = 0.0
    #: Cumulative entry fees (USD) for the current open position (long or short).
    #: Used to attribute fees into realized PnL on partial/total closes.
    entry_fee_usd: float = 0.0
    trades: List[Dict[str, Any]] = field(default_factory=list)
    #: Realized PnL per **sell** fill (USD), for win-rate on closed risk.
    realized_trade_pnls: List[float] = field(default_factory=list)
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    run_id: str = ""
    last_trade_step: int = -(10**9)

    def equity(self, current_price: float) -> float:
        return self.cash_usd + self.btc * current_price

    def record_trade(
        self,
        *,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        fee_usd: float,
        step: int | None,
        bar_ts_ms: int | None,
        sim_meta: dict[str, Any] | None = None,
    ) -> None:
        ts_ms = int(bar_ts_ms) if bar_ts_ms is not None else int(time.time() * 1000)
        seq = len(self.trades)
        row = build_binance_my_trades_row(
            symbol_ccxt=symbol,
            side=side,
            qty=qty,
            price=price,
            commission=float(fee_usd),
            commission_asset=quote_asset_from_ccxt(symbol),
            time_ms=ts_ms,
            is_maker=False,
            run_id=self.run_id or "sim",
            step=int(step if step is not None else 0),
            seq=seq,
            sim_meta=sim_meta,
        )
        self.trades.append(row)


@dataclass
class BacktestMultiSimState:
    cash_usd: float
    positions: Dict[str, float] = field(default_factory=dict)
    entry_avg: Dict[str, float] = field(default_factory=dict)
    #: Per-symbol locked initial margin (perp only).
    margin_locked: Dict[str, float] = field(default_factory=dict)
    trades: List[Dict[str, Any]] = field(default_factory=list)
    realized_trade_pnls: List[float] = field(default_factory=list)
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    run_id: str = ""
    last_trade_step_by_symbol: Dict[str, int] = field(default_factory=dict)
    instrument: str = "spot"
    leverage: float = 1.0

    def equity(self, last_closes: Dict[str, float]) -> float:
        if str(self.instrument).lower() != "perp":
            m = 0.0
            for sym, q in self.positions.items():
                px = float(last_closes.get(sym, 0.0))
                m += float(q) * px
            return self.cash_usd + m
        u = 0.0
        for sym, q in self.positions.items():
            px = float(last_closes.get(sym, 0.0))
            avg = float(self.entry_avg.get(sym, 0.0))
            u += float(q) * (px - avg)
        locked = sum(float(v) for v in self.margin_locked.values())
        return float(self.cash_usd) + locked + u

    def gross_exposure(self, last_closes: Dict[str, float]) -> float:
        """Sum of absolute notional across symbols (USD)."""
        g = 0.0
        for sym, q in self.positions.items():
            px = float(last_closes.get(sym, 0.0))
            g += abs(float(q) * px)
        return g

    def record_trade(
        self,
        *,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        fee_usd: float,
        step: int | None,
        bar_ts_ms: int | None,
        sim_meta: dict[str, Any] | None = None,
    ) -> None:
        ts_ms = int(bar_ts_ms) if bar_ts_ms is not None else int(time.time() * 1000)
        seq = len(self.trades)
        row = build_binance_my_trades_row(
            symbol_ccxt=symbol,
            side=side,
            qty=qty,
            price=price,
            commission=float(fee_usd),
            commission_asset=quote_asset_from_ccxt(symbol),
            time_ms=ts_ms,
            is_maker=False,
            run_id=self.run_id or "sim",
            step=int(step if step is not None else 0),
            seq=seq,
            sim_meta=sim_meta,
        )
        self.trades.append(row)


class BacktestEngine:
    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()
        self.sim: BacktestSimState | None = None
        self.multi_sim: BacktestMultiSimState | None = None
        self.workflow = build_workflow().compile()
        # Deterministic pseudo-randomness for fills. Seed is set per run_id in run()/_run_multi_asset().
        self._rng = random.Random(0)

    @staticmethod
    def _stable_seed(parts: tuple[Any, ...]) -> int:
        """Process-stable seed (avoid Python's randomized hash())."""
        blob = repr(parts).encode("utf-8", errors="ignore")
        h = hashlib.sha256(blob).digest()
        return int.from_bytes(h[:8], "big", signed=False)

    def _forced_risk_smart_order(
        self,
        bar: List[Any],
        *,
        pre_qty: float,
        pre_entry: float,
        policy: FundPolicy,
    ) -> tuple[dict[str, Any] | None, float | None]:
        """If bar range breaches stop or take-profit vs *pre-bar* entry, force a full exit.

        Uses intrabar **low** / **high** (OHLCV indices 3 / 2). Overrides a missed or vetoed
        graph order so the sim book cannot stay open through a stop level on that candle.
        Returns ``(smart_order_dict_or_none, fill_price_reference_or_none)``.
        """
        q = float(pre_qty)
        entry = float(pre_entry)
        if q <= 1e-12 or entry <= 1e-12:
            return None, None
        close = float(bar[4]) if len(bar) > 4 else 0.0
        low = float(bar[3]) if len(bar) > 3 else close
        high = float(bar[2]) if len(bar) > 2 else close
        stop_pct = float(policy.stop_loss_pct)
        tp_pct = float(policy.take_profit_pct)

        if stop_pct > 0:
            stop_line = entry * (1.0 - stop_pct)
            if low <= stop_line + 1e-12:
                fill_ref = min(close, stop_line)
                return (
                    {
                        "status": "accepted",
                        "mode": "backtest",
                        "venue": "sim",
                        "symbol": "engine_risk_bind",
                        "side": "sell",
                        "qty": q,
                        "type": "market",
                        "intent": {
                            "category": "risk_stop_loss",
                            "forced_by": "backtest_engine",
                            "stop_line": stop_line,
                            "bar_low": low,
                        },
                    },
                    fill_ref,
                )

        if tp_pct > 0:
            tp_line = entry * (1.0 + tp_pct)
            if high >= tp_line - 1e-12:
                fill_ref = max(close, tp_line)
                return (
                    {
                        "status": "accepted",
                        "mode": "backtest",
                        "venue": "sim",
                        "symbol": "engine_risk_bind",
                        "side": "sell",
                        "qty": q,
                        "type": "market",
                        "intent": {
                            "category": "risk_take_profit",
                            "forced_by": "backtest_engine",
                            "tp_line": tp_line,
                            "bar_high": high,
                        },
                    },
                    fill_ref,
                )

        return None, None

    def _simulate_fill(
        self,
        bar_close: float,
        side: str,
        requested_qty: float,
        *,
        price_reference: float | None = None,
        allow_partial: bool = True,
    ) -> tuple[float, float, float]:
        """Realistic fill with slippage, partial fill, and fees.

        ``price_reference`` (optional) anchors the mid before slippage (e.g. stop price);
        defaults to bar close.
        """
        base = float(price_reference) if price_reference is not None else float(bar_close)
        # Basis points as fraction of price (was wrongly: bps * price used as multiplier).
        slip_frac = self.config.slippage_bps / 10000.0
        fill_price = base * (1 + slip_frac) if side == "buy" else base * (1 - slip_frac)

        if allow_partial:
            # Deterministic partial fills (no time-dependence → reproducible backtests).
            fill_ratio = 0.93 + (self._rng.random() * 0.07)
            fill_qty = requested_qty * fill_ratio
        else:
            fill_qty = requested_qty

        fee_usd = fill_price * fill_qty * (self.config.fee_bps / 10000.0)
        return fill_price, fill_qty, fee_usd

    def _apply_multi_order_fill(
        self,
        sim: BacktestMultiSimState,
        *,
        smart_dict: dict[str, Any],
        symbol: str,
        bar_close: float,
        price_reference: float | None,
        last_closes: Dict[str, float],
        step: int,
        bar_ts_ms: int,
    ) -> bool:
        if smart_dict.get("status") != "accepted":
            return False
        qty_req = float(smart_dict.get("qty") or 0.0)
        if qty_req <= 1e-18:
            return False
        side = str(smart_dict.get("side") or "").lower()
        intent = smart_dict.get("intent") if isinstance(smart_dict.get("intent"), dict) else {}
        forced_by = str(intent.get("forced_by") or "")
        allow_partial = forced_by != "backtest_engine"
        fill_price, fill_qty, fee_usd = self._simulate_fill(
            bar_close,
            side,
            qty_req,
            price_reference=price_reference,
            allow_partial=allow_partial,
        )
        if side == "sell":
            held = float(sim.positions.get(symbol, 0.0) or 0.0)
            if str(getattr(self.config, "instrument", "spot")).lower() != "perp" or held > 1e-12:
                fill_qty = min(fill_qty, held, qty_req) if held > 1e-12 else fill_qty
            fee_usd = fill_price * fill_qty * (self.config.fee_bps / 10000.0)
        if side == "buy":
            held_b = float(sim.positions.get(symbol, 0.0) or 0.0)
            if (
                str(getattr(self.config, "instrument", "spot")).lower() == "perp"
                and held_b < -1e-12
            ):
                fill_qty = min(fill_qty, abs(held_b), qty_req)
                fee_usd = fill_price * fill_qty * (self.config.fee_bps / 10000.0)

        applied = False
        if str(getattr(self.config, "instrument", "spot")).lower() == "perp":
            pa = PaperAccount(
                cash_usdt=float(sim.cash_usd),
                realized_pnl_usdt=0.0,
                account_id=str(sim.run_id or "bt"),
            )
            for sym, q in sim.positions.items():
                if abs(float(q)) > 1e-18:
                    pa.perp_positions[sym] = PerpPosition(
                        symbol=str(sym),
                        qty_signed=float(q),
                        avg_entry=float(sim.entry_avg.get(sym, 0.0)),
                        leverage=max(1.0, float(sim.leverage)),
                        margin_locked_usdt=float(sim.margin_locked.get(sym, 0.0)),
                    )
            fp = load_fund_policy()
            lev = min(max(1.0, float(sim.leverage)), max(1.0, float(fp.max_leverage)))
            try:
                apply_perp_fill(
                    account=pa,
                    symbol=symbol,
                    side=side,
                    qty=float(fill_qty),
                    price=float(fill_price),
                    fee_bps=float(self.config.fee_bps),
                    leverage=float(lev),
                )
            except Exception:
                applied = False
            else:
                sim.cash_usd = float(pa.cash_usdt)
                sim.positions = {}
                sim.entry_avg = {}
                sim.margin_locked = {}
                for sym, p in pa.perp_positions.items():
                    sim.positions[sym] = float(p.qty_signed)
                    sim.entry_avg[sym] = float(p.avg_entry)
                    sim.margin_locked[sym] = float(p.margin_locked_usdt)
                applied = True
        elif side == "buy":
            cost = fill_price * fill_qty + fee_usd
            # Allow borrowed buying power up to FundPolicy.max_leverage (simple margin model).
            # Equity is computed from current positions + cash; leverage constrains gross exposure.
            fp = load_fund_policy()
            max_lev = max(1.0, float(fp.max_leverage))
            equity = float(sim.equity(last_closes))
            if equity <= 1e-9:
                equity = float(sim.cash_usd)
            borrow_limit = max(0.0, (max_lev - 1.0) * equity)
            # Also enforce gross exposure cap after this buy.
            pre_gross = float(sim.gross_exposure(last_closes))
            post_gross = pre_gross + float(fill_price * fill_qty)
            if (sim.cash_usd - cost) >= (-borrow_limit - 1e-6) and post_gross <= (
                max_lev * equity + 1e-6
            ):
                old_q = float(sim.positions.get(symbol, 0.0) or 0.0)
                old_e = float(sim.entry_avg.get(symbol, 0.0) or 0.0)
                sim.cash_usd -= cost
                new_q = old_q + fill_qty
                sim.positions[symbol] = new_q
                if new_q > 1e-12:
                    if old_q <= 1e-12:
                        sim.entry_avg[symbol] = fill_price
                    else:
                        sim.entry_avg[symbol] = (old_e * old_q + fill_price * fill_qty) / new_q
                applied = True
        elif side == "sell":
            held = float(sim.positions.get(symbol, 0.0) or 0.0)
            if held >= fill_qty - 1e-8:
                old_e = float(sim.entry_avg.get(symbol, 0.0) or 0.0)
                proceeds = fill_price * fill_qty - fee_usd
                cost_basis = old_e * fill_qty
                sim.realized_trade_pnls.append(float(proceeds - cost_basis))
                sim.positions[symbol] = held - fill_qty
                sim.cash_usd += proceeds
                if sim.positions[symbol] <= 1e-12:
                    del sim.positions[symbol]
                    sim.entry_avg.pop(symbol, None)
                else:
                    sim.entry_avg[symbol] = old_e
                applied = True

        if applied:
            # Mark churn control (step tracking is maintained by caller).
            intent = smart_dict.get("intent") if isinstance(smart_dict.get("intent"), dict) else {}
            sim_meta: Dict[str, Any] = {
                **intent,
                "venue": smart_dict.get("venue"),
                "mode": smart_dict.get("mode"),
                "order_type": smart_dict.get("type"),
                "instrument": str(getattr(self.config, "instrument", "spot")),
                "leverage": float(sim.leverage)
                if str(getattr(self.config, "instrument", "spot")).lower() == "perp"
                else None,
            }
            sim_meta = {k: v for k, v in sim_meta.items() if v is not None}
            sim.record_trade(
                symbol=symbol,
                side=side,
                qty=fill_qty,
                price=fill_price,
                fee_usd=fee_usd,
                step=step,
                bar_ts_ms=bar_ts_ms,
                sim_meta=sim_meta,
            )
        return applied

    def _run_multi_asset(
        self,
        *,
        ticker: str,
        bars_by_symbol: Dict[str, List[List[Any]]],
        run_id: str | None,
        runs_dir: Path | None,
    ) -> Dict[str, Any]:
        run_id = run_id or f"bt_{int(time.time())}"
        runs_dir = runs_dir or (self.config.runs_dir or Path(".runs"))
        runs_dir.mkdir(parents=True, exist_ok=True)
        (runs_dir / "latest_run.txt").write_text(run_id)

        normalized: dict[str, list[list[Any]]] = {
            str(sym): [list(row) for row in rows] for sym, rows in bars_by_symbol.items()
        }
        aligned = align_bars_by_min_length(normalized)
        symbols = sorted(aligned.keys())
        bars_primary = aligned[ticker]

        self.multi_sim = BacktestMultiSimState(
            cash_usd=self.config.initial_cash_usd,
            run_id=run_id,
            instrument=str(getattr(self.config, "instrument", "spot")),
            leverage=float(getattr(self.config, "leverage", 3.0)),
        )
        # Seed from the *data* (not run_id) so repeated runs are reproducible.
        seed = self._stable_seed(
            (
                str(ticker),
                int(bars_primary[0][0]),
                int(bars_primary[-1][0]),
                int(len(bars_primary)),
                tuple(symbols),
            )
        )
        self._rng.seed(int(seed) % (2**32))
        self.sim = None
        multi = self.multi_sim

        log_path = runs_dir / f"{run_id}.events.jsonl"
        if log_path.exists():
            log_path.unlink()
        flow_repo = FlowEventRepo(run_id=run_id, log_path=log_path)
        set_flow_repo(flow_repo)

        total_steps = min(self.config.max_steps or len(bars_primary), len(bars_primary))
        iteration_rows: list[dict[str, Any]] = []
        policy_bt = load_fund_policy()
        peak_equity = float(self.config.initial_cash_usd)
        halt_until_step = -1

        for step in range(total_steps):
            windows = {s: aligned[s][: step + 1] for s in symbols}
            last_closes = {s: float(windows[s][-1][4]) for s in symbols}
            primary_close = float(last_closes[ticker])
            eq_now = float(multi.equity(last_closes))
            if eq_now > peak_equity:
                peak_equity = eq_now
            dd_frac = (1.0 - (eq_now / peak_equity)) if peak_equity > 1e-9 else 0.0
            policy_bt = load_fund_policy()
            dd_stop = policy_bt.risk_max_drawdown_stop
            in_halt = step < int(halt_until_step)
            dd_triggered = False
            if dd_stop is not None and (not in_halt) and dd_frac >= float(dd_stop):
                dd_triggered = True
                halt_until_step = max(
                    int(halt_until_step),
                    step + int(policy_bt.risk_kill_switch_cooldown_bars or 0),
                )

            state = initial_hedge_fund_state(ticker=ticker, run_mode=RunMode.BACKTEST.value)
            state["universe"] = list(symbols)
            state["market_data"] = {
                s: {"status": "success", "backtest": True, "ohlcv": windows[s]} for s in symbols
            }
            sm = state.setdefault("shared_memory", {})
            sm["backtest"] = {
                "cash": float(multi.cash_usd),
                "positions": {k: float(v) for k, v in multi.positions.items()},
                "entry_avg_by_symbol": {k: float(v) for k, v in multi.entry_avg.items()},
            }

            output: Dict[str, Any]
            execution: Dict[str, Any]
            if in_halt or dd_triggered:
                output = {"execution_result": {}, "is_vetoed": True}
                execution = {}
            else:
                output = self.workflow.invoke(state)
                execution = output.get("execution_result", {}) or {}

            order_queue: list[tuple[dict[str, Any], float | None, str]] = []
            forced_syms: set[str] = set()

            # Portfolio max-drawdown stop: liquidate everything immediately.
            if dd_triggered:
                for sym in symbols:
                    held = float(multi.positions.get(sym, 0.0) or 0.0)
                    if held <= 1e-12:
                        continue
                    od = {
                        "status": "accepted",
                        "side": "sell",
                        "qty": float(held),
                        "symbol": sym,
                        "intent": {
                            "forced_by": "backtest_engine",
                            "category": "max_drawdown_stop",
                            "dd_frac": float(dd_frac),
                            "dd_stop": float(dd_stop) if dd_stop is not None else None,
                        },
                    }
                    order_queue.append((od, None, sym))
                    forced_syms.add(sym)
            for sym in symbols:
                pre_q = float(multi.positions.get(sym, 0.0) or 0.0)
                pre_e = float(multi.entry_avg.get(sym, 0.0) or 0.0)
                bar = windows[sym][-1]
                fo, ref = self._forced_risk_smart_order(
                    bar,
                    pre_qty=pre_q,
                    pre_entry=pre_e,
                    policy=policy_bt,
                )
                if fo is not None:
                    fo2 = dict(fo)
                    fo2["symbol"] = sym
                    order_queue.append((fo2, ref, sym))
                    forced_syms.add(sym)

            raw_list = execution.get("smart_orders")
            if not isinstance(raw_list, list):
                so = execution.get("smart_order")
                raw_list = [so] if isinstance(so, dict) else []
            graph_orders: list[dict[str, Any]] = []
            for od in raw_list:
                if not isinstance(od, dict):
                    continue
                sym_o = str(od.get("symbol") or ticker)
                if sym_o in forced_syms:
                    continue
                graph_orders.append(od)

            sells = [o for o in graph_orders if str(o.get("side") or "").lower() == "sell"]
            buys = [o for o in graph_orders if str(o.get("side") or "").lower() == "buy"]
            other = [o for o in graph_orders if o not in sells and o not in buys]
            in_halt = step < int(halt_until_step)
            for od in sells + ([] if in_halt else buys) + ([] if in_halt else other):
                sym_o = str(od.get("symbol") or ticker)
                order_queue.append((od, None, sym_o))

            display_smart = graph_orders[0] if graph_orders else None
            engine_forced: str | None = None
            for od, ref, sym_o in order_queue:
                # Churn control: per-symbol cooldown.
                policy_bt = load_fund_policy()
                cooldown = int(policy_bt.trade_cooldown_bars or 0)
                if cooldown > 0:
                    last = int(multi.last_trade_step_by_symbol.get(sym_o, -(10**9)))
                    if step - last < cooldown:
                        continue
                intent = od.get("intent") if isinstance(od.get("intent"), dict) else {}
                if engine_forced is None and intent.get("forced_by") == "backtest_engine":
                    engine_forced = str(intent.get("category") or "risk_exit")
                bar_c = float(last_closes.get(sym_o, 0.0))
                bar_row = windows[sym_o][-1]
                bar_ts_ms = int(bar_row[0]) if bar_row else int(time.time() * 1000)
                try:
                    did = self._apply_multi_order_fill(
                        multi,
                        smart_dict=od,
                        symbol=sym_o,
                        bar_close=bar_c,
                        price_reference=ref,
                        last_closes=last_closes,
                        step=step,
                        bar_ts_ms=bar_ts_ms,
                    )
                    if did and cooldown > 0:
                        multi.last_trade_step_by_symbol[sym_o] = step
                except Exception as e:
                    print(f"[Backtest Warning] Invalid smart_order at step {step}: {e}")

            multi.equity_curve.append(
                {
                    "timestamp": int(windows[ticker][-1][0]),
                    "price": primary_close,
                    "equity": multi.equity(last_closes),
                    "cash": multi.cash_usd,
                    "positions": dict(multi.positions),
                    "dd_frac": float(dd_frac),
                    "dd_halt": bool(in_halt),
                }
            )

            iteration_rows.append(
                {
                    "step": step,
                    "bar_ts_ms": int(windows[ticker][-1][0]),
                    "close": primary_close,
                    "desk_debate": _compact_debate_for_iteration(output),
                    "trade_intent": output.get("trade_intent"),
                    "proposed_signal": _compact_proposed_for_iteration(
                        output.get("proposed_signal")
                    ),
                    "signal_arbitrator": _compact_signal_arbitrator_upstream(output),
                    "llm_arbitrator": _llm_arbitrator_used(output),
                    "is_vetoed": bool(output.get("is_vetoed")),
                    "execution_status": (output.get("execution_result") or {}).get("status"),
                    "smart_order": _compact_smart_order(display_smart),
                    "engine_forced_risk_exit": engine_forced,
                    "trade_count_so_far": len(multi.trades),
                    "dd_frac": float(dd_frac),
                    "dd_halt": bool(in_halt),
                }
            )

            if self.config.progress_callback:
                snap = {
                    **multi.equity_curve[-1],
                    "trade_count": len(multi.trades),
                    "vetoed": bool(output.get("is_vetoed")),
                }
                self.config.progress_callback(step + 1, total_steps, snap)

        equity_vals = [
            float(p.get("equity", 0.0)) for p in (multi.equity_curve or []) if isinstance(p, dict)
        ]
        metrics = compute_basic_metrics(
            equity_curve=equity_vals,
            trade_pnls=multi.realized_trade_pnls,
            interval_sec=int(self.config.interval_sec),
        )

        initial_usd = float(self.config.initial_cash_usd)
        last_closes_final = {s: float(aligned[s][-1][4]) for s in symbols}
        final_strat = float(multi.equity(last_closes_final))
        strategy_ret_pct = (
            ((final_strat - initial_usd) / initial_usd * 100.0) if initial_usd > 0 else 0.0
        )
        bench: dict[str, Any] = dict(
            compute_buy_hold_benchmark(
                initial_cash_usd=initial_usd,
                bars=bars_primary,
                fee_bps=float(self.config.fee_bps),
                slippage_bps=float(self.config.slippage_bps),
            )
        )
        bench["strategy_total_return_pct"] = round(strategy_ret_pct, 6)
        bh_eq = bench.get("benchmark_buy_hold_equity_return_pct")
        if bh_eq is not None:
            bench["excess_return_vs_buy_hold_equity_pct"] = round(
                strategy_ret_pct - float(bh_eq), 6
            )

        ew = compute_equal_weight_buy_hold_benchmark(
            initial_cash_usd=initial_usd,
            bars_by_symbol=aligned,
            fee_bps=float(self.config.fee_bps),
            slippage_bps=float(self.config.slippage_bps),
        )
        if ew:
            bench.update(ew)
            ew_eq = ew.get("benchmark_equal_weight_equity_return_pct")
            if ew_eq is not None:
                bench["excess_return_vs_equal_weight_equity_pct"] = round(
                    strategy_ret_pct - float(ew_eq), 6
                )
        if ew and bench.get("benchmark_buy_hold_equity_return_pct") is not None:
            bench["benchmark_scope"] = "primary_ticker_bh_plus_equal_weight_portfolio_bh"
        elif ew:
            bench["benchmark_scope"] = "equal_weight_portfolio_bh"
        elif bench.get("benchmark_buy_hold_equity_return_pct") is not None:
            bench["benchmark_scope"] = "primary_ticker_only"
        else:
            bench["benchmark_scope"] = "strategy_return_only"

        job_dir = runs_dir / "backtests" / run_id
        job_dir.mkdir(parents=True, exist_ok=True)
        trades_path = job_dir / "trades.jsonl"
        trades_csv_path = job_dir / "trades.csv"
        equity_path = job_dir / "equity.jsonl"
        iterations_path = job_dir / "iterations.jsonl"
        bars_path = job_dir / "bars.json"
        write_jsonl_records(trades_path, multi.trades)
        trades_csv_path.write_text(trades_to_csv(multi.trades), encoding="utf-8")
        write_jsonl_records(equity_path, multi.equity_curve)
        bars_primary = aligned.get(ticker) or []
        bars_payload = {
            "ticker": str(ticker),
            "interval_sec": int(self.config.interval_sec),
            "bars": [
                {
                    "step": i,
                    "ts_ms": float(row[0]),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]) if len(row) > 5 else 0.0,
                }
                for i, row in enumerate(bars_primary)
                if isinstance(row, (list, tuple)) and len(row) >= 5
            ],
        }
        bars_path.write_text(json.dumps(bars_payload), encoding="utf-8")
        iterations_path.write_text(
            "".join(json.dumps(r, default=str) + "\n" for r in iteration_rows),
            encoding="utf-8",
        )

        manifest = None
        if self.config.export_bundle:
            manifest = export_run_bundle(
                run_id=run_id, out_dir=runs_dir / "bundles", runs_base=runs_dir
            )

        summary_path = job_dir / "summary.json"
        summary = {
            "run_id": run_id,
            "steps": total_steps,
            "trade_count": len(multi.trades),
            "instrument": str(getattr(self.config, "instrument", "spot")),
            "leverage": float(getattr(self.config, "leverage", 1.0)),
            "metrics": asdict(metrics),
            "benchmark": bench,
            "multi_asset": True,
            "universe": list(symbols),
            "paths": {
                "trades": str(trades_path),
                "trades_csv": str(trades_csv_path),
                "equity": str(equity_path),
                "bars": str(bars_path),
                "iterations": str(iterations_path),
                "events": str(log_path),
            },
        }
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        return {
            "run_id": run_id,
            "steps": total_steps,
            "interval_sec": int(self.config.interval_sec),
            "trade_count": len(multi.trades),
            "metrics": asdict(metrics),
            "final_equity": multi.equity(last_closes_final),
            "benchmark": bench,
            "paths": {
                "summary": str(job_dir / "summary.json"),
                "trades": str(trades_path),
                "trades_csv": str(trades_csv_path),
                "equity": str(equity_path),
                "bars": str(bars_path),
                "iterations": str(iterations_path),
                "events": str(log_path),
            },
            "bundle_manifest": manifest,
        }

    def run(
        self,
        ticker: str = "BTC/USDT",
        bars: List[List[Any]] | None = None,
        bars_by_symbol: Dict[str, List[List[Any]]] | None = None,
        run_id: str | None = None,
        runs_dir: Path | None = None,
    ) -> Dict[str, Any]:
        if bars_by_symbol is not None:
            if not bars_by_symbol:
                raise ValueError("bars_by_symbol must be non-empty")
            if ticker not in bars_by_symbol:
                raise ValueError(f"ticker {ticker!r} must be a key in bars_by_symbol")
            return self._run_multi_asset(
                ticker=ticker,
                bars_by_symbol=bars_by_symbol,
                run_id=run_id,
                runs_dir=runs_dir,
            )

        if bars is None or len(bars) == 0:
            raise ValueError("bars must be provided (use bars.py loader if needed)")

        run_id = run_id or f"bt_{int(time.time())}"
        runs_dir = runs_dir or (self.config.runs_dir or Path(".runs"))
        runs_dir.mkdir(parents=True, exist_ok=True)
        (runs_dir / "latest_run.txt").write_text(run_id)

        self.multi_sim = None
        self.sim = BacktestSimState(
            cash_usd=self.config.initial_cash_usd,
            btc=self.config.initial_btc,
            run_id=run_id,
        )
        # Seed from the *data* (not run_id) so repeated runs are reproducible.
        seed = self._stable_seed(
            (
                str(ticker),
                int(bars[0][0]) if bars else 0,
                int(bars[-1][0]) if bars else 0,
                int(len(bars)) if bars else 0,
            )
        )
        self._rng.seed(int(seed) % (2**32))
        if self.sim.btc > 1e-12 and self.sim.entry_avg_price <= 1e-12 and bars:
            self.sim.entry_avg_price = float(bars[0][4])

        log_path = runs_dir / f"{run_id}.events.jsonl"
        if log_path.exists():
            log_path.unlink()
        flow_repo = FlowEventRepo(run_id=run_id, log_path=log_path)
        set_flow_repo(flow_repo)

        total_steps = min(self.config.max_steps or len(bars), len(bars))
        iteration_rows: list[dict[str, Any]] = []

        policy_bt = load_fund_policy()
        peak_equity = float(self.config.initial_cash_usd)
        halt_until_step = -1

        for step in range(total_steps):
            ohlcv_window = bars[: step + 1]
            current_price = float(ohlcv_window[-1][4])  # close price
            pre_qty = float(self.sim.btc)
            pre_entry = float(self.sim.entry_avg_price)
            eq_now = float(self.sim.equity(current_price))
            if eq_now > peak_equity:
                peak_equity = eq_now
            dd_frac = (1.0 - (eq_now / peak_equity)) if peak_equity > 1e-9 else 0.0
            policy_bt = load_fund_policy()
            dd_stop = policy_bt.risk_max_drawdown_stop
            in_halt = step < int(halt_until_step)
            dd_triggered = False
            if dd_stop is not None and (not in_halt) and dd_frac >= float(dd_stop):
                dd_triggered = True
                halt_until_step = max(
                    int(halt_until_step),
                    step + int(policy_bt.risk_kill_switch_cooldown_bars or 0),
                )

            # Build state consistently with live mode
            state = initial_hedge_fund_state(ticker=ticker, run_mode=RunMode.BACKTEST.value)
            state["market_data"] = {
                ticker: {
                    "status": "success",
                    "backtest": True,
                    "ohlcv": ohlcv_window,
                }
            }
            sm = state.setdefault("shared_memory", {})
            sm["backtest"] = {
                "cash": float(self.sim.cash_usd),
                "qty": float(self.sim.btc),
                "entry_avg_price": float(self.sim.entry_avg_price),
            }

            # Run full workflow unless halted.
            if in_halt or dd_triggered:
                output = {"execution_result": {}, "is_vetoed": True}
            else:
                output = self.workflow.invoke(state)

            # Authoritative TradeIntent handling
            execution = output.get("execution_result", {}) or {}
            smart_dict = execution.get("smart_order")

            forced_order, forced_fill_ref = self._forced_risk_smart_order(
                ohlcv_window[-1],
                pre_qty=pre_qty,
                pre_entry=pre_entry,
                policy=policy_bt,
            )
            engine_forced: str | None = None
            if forced_order is not None:
                smart_dict = forced_order
                if isinstance((forced_order.get("intent") or {}), dict):
                    engine_forced = str(
                        (forced_order["intent"] or {}).get("category") or "risk_exit"
                    )

            # Portfolio max-drawdown stop: liquidate immediately.
            if dd_triggered and pre_qty > 1e-12:
                smart_dict = {
                    "status": "accepted",
                    "side": "sell",
                    "qty": float(abs(pre_qty)),
                    "intent": {
                        "forced_by": "backtest_engine",
                        "category": "max_drawdown_stop",
                        "dd_frac": float(dd_frac),
                        "dd_stop": float(dd_stop) if dd_stop is not None else None,
                    },
                }
                forced_fill_ref = None
                engine_forced = "max_drawdown_stop"

            if smart_dict:
                try:
                    if (
                        isinstance(smart_dict, dict)
                        and smart_dict.get("status") == "accepted"
                        and float(smart_dict.get("qty") or 0.0) > 0
                    ):
                        side = str(smart_dict.get("side") or "").lower()
                        qty = float(smart_dict.get("qty") or 0.0)
                        if in_halt and side == "buy":
                            smart_dict = None
                            raise RuntimeError("halted")
                        intent = (
                            smart_dict.get("intent")
                            if isinstance(smart_dict.get("intent"), dict)
                            else {}
                        )
                        forced_by = str(intent.get("forced_by") or "")
                        allow_partial = forced_by != "backtest_engine"
                        fill_price, fill_qty_total, fee_total = self._simulate_fill(
                            current_price,
                            side,
                            qty,
                            price_reference=forced_fill_ref if forced_order is not None else None,
                            allow_partial=allow_partial,
                        )

                        cooldown = int(load_fund_policy().trade_cooldown_bars or 0)
                        if cooldown > 0 and (step - int(self.sim.last_trade_step)) < cooldown:
                            # Skip this fill to avoid churn.
                            fill_qty_total = 0.0

                        applied = False
                        if fill_qty_total > 1e-18 and side == "buy":
                            cost = fill_price * fill_qty_total + fee_total
                            if cost <= self.sim.cash_usd + 1e-6:
                                old_pos = float(self.sim.btc)
                                old_entry = float(self.sim.entry_avg_price)
                                old_entry_fee = float(self.sim.entry_fee_usd)
                                self.sim.cash_usd -= cost

                                # Cover shorts first (if any), then potentially open/extend long.
                                if old_pos < -1e-12:
                                    cover_qty = min(fill_qty_total, abs(old_pos))
                                    fee_close = (
                                        fee_total * (cover_qty / fill_qty_total)
                                        if fill_qty_total > 1e-18
                                        else 0.0
                                    )
                                    # Attribute a proportional share of entry fees to this close.
                                    fee_alloc = 0.0
                                    if abs(old_pos) > 1e-12 and old_entry_fee > 0:
                                        fee_alloc = old_entry_fee * (cover_qty / abs(old_pos))
                                    # Short PnL: entry sell price - cover buy price, minus fees.
                                    realized = (
                                        (old_entry - fill_price) * cover_qty - fee_close - fee_alloc
                                    )
                                    self.sim.realized_trade_pnls.append(float(realized))

                                    new_pos = old_pos + cover_qty  # less negative
                                    self.sim.btc = new_pos
                                    self.sim.entry_fee_usd = max(0.0, old_entry_fee - fee_alloc)
                                    open_qty = fill_qty_total - cover_qty
                                    fee_open = fee_total - fee_close

                                    if abs(self.sim.btc) <= 1e-12:
                                        self.sim.btc = 0.0
                                        self.sim.entry_avg_price = 0.0
                                        self.sim.entry_fee_usd = 0.0
                                else:
                                    open_qty = fill_qty_total
                                    fee_open = fee_total

                                # Any remaining buy qty opens/adds to long.
                                if open_qty > 1e-18:
                                    old_pos2 = float(self.sim.btc)
                                    if old_pos2 < 1e-12:
                                        self.sim.entry_avg_price = fill_price
                                        self.sim.entry_fee_usd = fee_open
                                        self.sim.btc = old_pos2 + open_qty
                                    else:
                                        new_pos2 = old_pos2 + open_qty
                                        self.sim.entry_avg_price = (
                                            self.sim.entry_avg_price * old_pos2
                                            + fill_price * open_qty
                                        ) / new_pos2
                                        self.sim.entry_fee_usd += fee_open
                                        self.sim.btc = new_pos2
                                applied = True
                        elif fill_qty_total > 1e-18 and side == "sell":
                            old_pos = float(self.sim.btc)
                            old_entry = float(self.sim.entry_avg_price)
                            old_entry_fee = float(self.sim.entry_fee_usd)

                            # Long-only cap unless shorts are allowed.
                            if old_pos > 1e-12 or not policy_bt.allows_short:
                                fill_qty_total = min(fill_qty_total, max(0.0, old_pos), qty)
                                fee_total = (
                                    fill_price * fill_qty_total * (self.config.fee_bps / 10000.0)
                                )

                            if fill_qty_total > 1e-18:
                                proceeds = fill_price * fill_qty_total - fee_total
                                self.sim.cash_usd += proceeds

                                if old_pos > 1e-12:
                                    close_qty = min(fill_qty_total, old_pos)
                                    fee_close = (
                                        fee_total * (close_qty / fill_qty_total)
                                        if fill_qty_total > 1e-18
                                        else 0.0
                                    )
                                    fee_alloc = 0.0
                                    if old_pos > 1e-12 and old_entry_fee > 0:
                                        fee_alloc = old_entry_fee * (close_qty / old_pos)
                                    realized = (
                                        (fill_price - old_entry) * close_qty - fee_close - fee_alloc
                                    )
                                    self.sim.realized_trade_pnls.append(float(realized))
                                    self.sim.entry_fee_usd = max(0.0, old_entry_fee - fee_alloc)
                                    old_pos -= close_qty
                                    open_qty = fill_qty_total - close_qty
                                    fee_open = fee_total - fee_close

                                    if old_pos <= 1e-12:
                                        old_pos = 0.0
                                        self.sim.entry_avg_price = 0.0
                                        self.sim.entry_fee_usd = 0.0
                                else:
                                    open_qty = fill_qty_total
                                    fee_open = fee_total

                                # Remaining sell qty opens/adds to short (if allowed).
                                if open_qty > 1e-18:
                                    if not policy_bt.allows_short:
                                        open_qty = 0.0
                                    else:
                                        # Add/establish short at fill_price; track VWAP by absolute size.
                                        cur_short = -old_pos if old_pos < -1e-12 else 0.0
                                        new_short = cur_short + open_qty
                                        if new_short > 1e-12:
                                            if cur_short <= 1e-12:
                                                self.sim.entry_avg_price = fill_price
                                                self.sim.entry_fee_usd = fee_open
                                            else:
                                                self.sim.entry_avg_price = (
                                                    old_entry * cur_short + fill_price * open_qty
                                                ) / new_short
                                                self.sim.entry_fee_usd += fee_open
                                        self.sim.btc = -new_short
                                else:
                                    self.sim.btc = old_pos
                                applied = True

                        if applied:
                            sd = smart_dict if isinstance(smart_dict, dict) else {}
                            intent = sd.get("intent") if isinstance(sd.get("intent"), dict) else {}
                            sim_meta = {
                                **intent,
                                "venue": sd.get("venue"),
                                "mode": sd.get("mode"),
                                "order_type": sd.get("type"),
                            }
                            sim_meta = {k: v for k, v in sim_meta.items() if v is not None}
                            self.sim.record_trade(
                                symbol=ticker,
                                side=side,
                                qty=fill_qty_total,
                                price=fill_price,
                                fee_usd=fee_total,
                                step=step,
                                bar_ts_ms=int(ohlcv_window[-1][0]),
                                sim_meta=sim_meta,
                            )
                            if cooldown > 0:
                                self.sim.last_trade_step = step
                except Exception as e:
                    print(f"[Backtest Warning] Invalid smart_order at step {step}: {e}")

            # Record equity
            self.sim.equity_curve.append(
                {
                    "timestamp": int(ohlcv_window[-1][0]),
                    "price": current_price,
                    "equity": self.sim.equity(current_price),
                    "cash": self.sim.cash_usd,
                    "btc": self.sim.btc,
                    "dd_frac": float(dd_frac),
                    "dd_halt": bool(in_halt),
                }
            )

            iteration_rows.append(
                {
                    "step": step,
                    "bar_ts_ms": int(ohlcv_window[-1][0]),
                    "close": current_price,
                    "desk_debate": _compact_debate_for_iteration(output),
                    "trade_intent": output.get("trade_intent"),
                    "proposed_signal": _compact_proposed_for_iteration(
                        output.get("proposed_signal")
                    ),
                    "signal_arbitrator": _compact_signal_arbitrator_upstream(output),
                    "llm_arbitrator": _llm_arbitrator_used(output),
                    "is_vetoed": bool(output.get("is_vetoed")),
                    "execution_status": (output.get("execution_result") or {}).get("status"),
                    "smart_order": _compact_smart_order(smart_dict),
                    "engine_forced_risk_exit": engine_forced,
                    "trade_count_so_far": len(self.sim.trades),
                    "dd_frac": float(dd_frac),
                    "dd_halt": bool(in_halt),
                }
            )

            if self.config.progress_callback:
                snap = {
                    **self.sim.equity_curve[-1],
                    "trade_count": len(self.sim.trades),
                    "vetoed": bool(output.get("is_vetoed")),
                }
                self.config.progress_callback(step + 1, total_steps, snap)

        equity_vals = [
            float(p.get("equity", 0.0))
            for p in (self.sim.equity_curve or [])
            if isinstance(p, dict)
        ]
        metrics = compute_basic_metrics(
            equity_curve=equity_vals,
            trade_pnls=self.sim.realized_trade_pnls,
            interval_sec=int(self.config.interval_sec),
        )

        first_close_b = float(bars[0][4]) if bars else 0.0
        initial_equity = (
            float(self.config.initial_cash_usd) + float(self.config.initial_btc) * first_close_b
        )
        last_close = float(bars[-1][4]) if bars else 0.0
        final_strat = float(self.sim.equity(last_close))
        strategy_ret_pct = (
            ((final_strat - initial_equity) / initial_equity * 100.0) if initial_equity > 0 else 0.0
        )
        bench: dict[str, Any] = dict(
            compute_buy_hold_benchmark(
                initial_cash_usd=initial_equity,
                bars=bars,
                fee_bps=float(self.config.fee_bps),
                slippage_bps=float(self.config.slippage_bps),
            )
        )
        if bench:
            bench["strategy_total_return_pct"] = round(strategy_ret_pct, 6)
            bench["benchmark_initial_equity_usd"] = round(initial_equity, 2)
            bh_eq = bench.get("benchmark_buy_hold_equity_return_pct")
            if bh_eq is not None:
                bench["excess_return_vs_buy_hold_equity_pct"] = round(
                    strategy_ret_pct - float(bh_eq), 6
                )

        job_dir = runs_dir / "backtests" / run_id
        job_dir.mkdir(parents=True, exist_ok=True)
        trades_path = job_dir / "trades.jsonl"
        trades_csv_path = job_dir / "trades.csv"
        equity_path = job_dir / "equity.jsonl"
        iterations_path = job_dir / "iterations.jsonl"
        bars_path = job_dir / "bars.json"
        write_jsonl_records(trades_path, self.sim.trades)
        trades_csv_path.write_text(trades_to_csv(self.sim.trades), encoding="utf-8")
        write_jsonl_records(equity_path, self.sim.equity_curve)
        bars_payload = {
            "ticker": str(ticker),
            "interval_sec": int(self.config.interval_sec),
            "bars": [
                {
                    "step": i,
                    "ts_ms": float(row[0]),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]) if len(row) > 5 else 0.0,
                }
                for i, row in enumerate(bars)
                if isinstance(row, (list, tuple)) and len(row) >= 5
            ],
        }
        bars_path.write_text(json.dumps(bars_payload), encoding="utf-8")
        iterations_path.write_text(
            "".join(json.dumps(r, default=str) + "\n" for r in iteration_rows),
            encoding="utf-8",
        )

        manifest = None
        if self.config.export_bundle:
            manifest = export_run_bundle(
                run_id=run_id, out_dir=runs_dir / "bundles", runs_base=runs_dir
            )

        summary_path = job_dir / "summary.json"
        summary = {
            "run_id": run_id,
            "steps": total_steps,
            "trade_count": len(self.sim.trades),
            "metrics": asdict(metrics),
            "benchmark": bench,
            "paths": {
                "trades": str(trades_path),
                "trades_csv": str(trades_csv_path),
                "equity": str(equity_path),
                "bars": str(bars_path),
                "iterations": str(iterations_path),
                "events": str(log_path),
            },
        }
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        return {
            "run_id": run_id,
            "steps": total_steps,
            "interval_sec": int(self.config.interval_sec),
            "trade_count": len(self.sim.trades),
            "metrics": asdict(metrics),
            "final_equity": self.sim.equity(float(bars[-1][4]) if bars else 0.0),
            "benchmark": bench,
            "paths": {
                "summary": str(job_dir / "summary.json"),
                "trades": str(trades_path),
                "trades_csv": str(trades_csv_path),
                "equity": str(equity_path),
                "bars": str(bars_path),
                "iterations": str(iterations_path),
                "events": str(log_path),
            },
            "bundle_manifest": manifest,
        }
