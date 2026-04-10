from __future__ import annotations

import os
from typing import Any, Dict

from agents.base_agent import BaseAgent
from config.fund_policy import load_fund_policy


def _env_truthy(name: str) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    return v in ("1", "true", "yes", "on")


class RiskGuardAgent(BaseAgent):
    """
    Governance layer: implements veto power (final say).
    """

    def __init__(self):
        super().__init__("Risk Guard", "Risk Officer")

    async def process(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Implements Veto Power.
        Expects a 'proposal' (e.g., orders/portfolio actions) and returns APPROVED/VETOED.
        """
        if _env_truthy("AIMM_KILL_SWITCH") or _env_truthy("AIMM_RISK_GUARD_KILL_SWITCH"):
            thought = (
                "Kill switch env is active (AIMM_KILL_SWITCH or AIMM_RISK_GUARD_KILL_SWITCH); "
                "all execution proposals vetoed."
            )
            return {
                "status": "VETOED",
                "risk_score": 1.0,
                "reasoning": self.log_reasoning(thought, "VETO"),
                "kill_switch": True,
            }

        risk_score, thought_extra = self._calculate_risk(proposal)

        is_vetoed = risk_score > 0.8
        thought = (
            f"Risk score is {risk_score:.2f}. "
            f"{'VETOED due to high risk/volatility' if is_vetoed else 'APPROVED'}"
        )

        return {
            "status": "VETOED" if is_vetoed else "APPROVED",
            "risk_score": risk_score,
            "reasoning": {
                **self.log_reasoning(thought, "VETO" if is_vetoed else "PROCEED"),
                "extra": thought_extra,
            },
        }

    def _calculate_risk(self, data: Dict[str, Any]) -> tuple[float, dict[str, Any]]:
        """Compute a conservative risk score from current portfolio snapshot + policy.

        Input contract (best-effort):
        - data["proposal"]: portfolio proposal dict (may include 'trades')
        - data["shared_memory"]: may include live/bt portfolio snapshot
        """
        fp = load_fund_policy()
        sm = data.get("shared_memory") if isinstance(data, dict) else None
        smd = sm if isinstance(sm, dict) else {}
        bt = smd.get("backtest") if isinstance(smd.get("backtest"), dict) else {}
        # Generic portfolio snapshot keys (works for backtest engine; live can adopt same schema).
        cash = bt.get("cash")
        positions = bt.get("positions")
        md = data.get("market_data")
        last_closes: dict[str, float] = {}
        if isinstance(md, dict):
            for sym, blob in md.items():
                if not isinstance(blob, dict):
                    continue
                ohlcv = blob.get("ohlcv")
                if isinstance(ohlcv, list) and ohlcv:
                    last = ohlcv[-1]
                    if isinstance(last, (list, tuple)) and len(last) > 4:
                        try:
                            last_closes[str(sym)] = float(last[4])
                        except (TypeError, ValueError):
                            pass

        equity = None
        gross = None
        try:
            cash_f = float(cash) if cash is not None else None
        except (TypeError, ValueError):
            cash_f = None
        if isinstance(positions, dict) and cash_f is not None and last_closes:
            m = 0.0
            g = 0.0
            for sym, q in positions.items():
                try:
                    qf = float(q)
                except (TypeError, ValueError):
                    continue
                px = float(last_closes.get(str(sym), 0.0))
                m += qf * px
                g += abs(qf * px)
            equity = cash_f + m
            gross = g

        # Drawdown stop is enforced in the engine, but in live mode we also want governance veto.
        dd_stop = fp.risk_max_drawdown_stop
        dd_frac = None
        peak = None
        if isinstance(bt, dict):
            peak = bt.get("equity_peak")
            dd_frac = bt.get("dd_frac")
        risk = 0.0
        reasons: list[str] = []

        if dd_stop is not None:
            # If dd_frac isn't provided, approximate from peak/equity when available.
            try:
                if dd_frac is None and peak is not None and equity is not None:
                    pk = float(peak)
                    if pk > 1e-9:
                        dd_frac = 1.0 - (float(equity) / pk)
                if dd_frac is not None and float(dd_frac) >= float(dd_stop):
                    risk = 1.0
                    reasons.append(
                        f"drawdown_stop_triggered dd={float(dd_frac):.3f} >= {float(dd_stop):.3f}"
                    )
            except (TypeError, ValueError):
                pass

        # Leverage / exposure gate (soft).
        if risk < 1.0 and equity is not None and gross is not None and float(equity) > 1e-9:
            lev = float(gross) / float(equity)
            # Penalize if near/exceed policy leverage.
            max_lev = max(1.0, float(fp.max_leverage))
            if lev > max_lev * 1.02:
                risk = max(risk, 0.95)
                reasons.append(f"gross_leverage_exceeded lev={lev:.2f} > {max_lev:.2f}")
            elif lev > max_lev * 0.90:
                risk = max(risk, 0.75)
                reasons.append(f"gross_leverage_high lev={lev:.2f} ~ {max_lev:.2f}")

        # If we can't compute anything, return a mild risk (do not veto).
        if not reasons and risk <= 0.0:
            risk = 0.35
            reasons.append("insufficient_portfolio_snapshot; default_caution")

        extra = {
            "equity": equity,
            "gross_exposure": gross,
            "dd_frac": dd_frac,
            "dd_stop": dd_stop,
            "reasons": reasons[:8],
        }
        return float(max(0.0, min(1.0, risk))), extra
