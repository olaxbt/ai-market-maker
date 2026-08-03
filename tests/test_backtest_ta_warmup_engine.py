"""Engine respects TA warmup: no workflow during warmup bars."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from backtest.engine import BacktestEngine


def _bars(n: int, *, start: float = 50_000.0) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(n):
        p = start + i * 10.0
        ts = 1_700_000_000_000 + i * 86_400_000
        out.append([ts, p, p + 5, p - 5, p, 100.0])
    return out


def test_warmup_bars_skip_workflow(monkeypatch):
    """Bars before min_warmup must not invoke LangGraph."""
    calls: list[int] = []

    monkeypatch.setenv("MODE", "backtest")
    monkeypatch.setenv("AIMM_BACKTEST_TERMINAL_LOG", "0")

    class _FakeWorkflow:
        def invoke(self, state):
            calls.append(
                int(state.get("shared_memory", {}).get("backtest", {}).get("window_len") or 0)
            )
            return {
                "trade_intent": {"action": "BUY", "confidence": 0.7},
                "tier0_contracts": [],
                "arbitration_result": {"composite": 60, "confidence": 0.7, "stance": "bullish"},
            }

    monkeypatch.setattr(
        "main.build_workflow",
        lambda: MagicMock(compile=lambda: _FakeWorkflow()),
    )

    with tempfile.TemporaryDirectory() as tmp:
        runs = Path(tmp)
        eng = BacktestEngine(
            {
                "initial_cash_usd": 10_000,
                "min_warmup_bars": 5,
                "eval_steps": 8,
                "ta_warmup_bars": 5,
                "deploy_profile_weights": {"2.3": 1.0},
                "interval_sec": 86_400,
            }
        )
        eng.workflow = _FakeWorkflow()
        res = eng.run(
            ticker="BTC/USDT",
            bars=_bars(13),
            runs_dir=runs,
            run_id="bt_warmup_test",
        )
        assert res["ta_warmup_bars"] == 5
        assert res["eval_bars"] == 8
        assert all(w >= 5 for w in calls)
        assert len(calls) > 0

        it_path = runs / "backtests" / "bt_warmup_test" / "iterations.jsonl"
        if it_path.is_file():
            rows = [json.loads(line) for line in it_path.read_text().splitlines() if line.strip()]
            assert all(int(r.get("bar_index", 0)) >= 5 for r in rows)
