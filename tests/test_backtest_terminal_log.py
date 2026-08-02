"""Tests for backtest terminal transcript."""

from __future__ import annotations

import io
import logging

from backtest.terminal_log import (
    configure_backtest_terminal_logging,
    print_bar_decision,
    print_run_summary,
)


def test_print_bar_decision_includes_cot(monkeypatch):
    monkeypatch.setenv("MODE", "backtest")
    monkeypatch.setenv("AIMM_BACKTEST_TERMINAL_LOG", "1")
    configure_backtest_terminal_logging()
    buf = io.StringIO()
    wf = {
        "profile_weights": {"2.3": 0.55, "2.1": 0.15, "1.1": 0.25},
        "tier0_contracts": [
            {
                "agent_id": "2.3",
                "label": "Technical TA Engine",
                "composite": 61.2,
                "stance": "bullish",
                "source": "agent_llm",
                "reasoning": "RSI neutral; MACD histogram turning positive.",
            },
            {"agent_id": "4.2", "status": "skipped", "source": None},
        ],
        "arbitration_result": {"composite": 58.0, "confidence": 0.68, "stance": "bullish"},
        "trade_intent": {"action": "BUY", "confidence": 0.68},
    }
    print_bar_decision(
        bar_index=10,
        total_bars=90,
        symbol="BTC/USDT",
        close=67432.0,
        ts_ms=1_781_827_200_000,
        wf_output=wf,
        action="BUY",
        confidence=0.68,
        equity=10_842.0,
        trade_count=3,
        stream=buf,
    )
    text = buf.getvalue()
    assert "Bar   10/90" in text
    assert "BTC/USDT" in text
    assert "2.3" in text
    assert "MACD histogram" in text
    assert "4.2" not in text
    assert "Desk deliberation" in text
    assert "Decision: BUY" in text
    assert "equity $10,842.00" in text
    assert "comp  61/100" in text or "comp 61/100" in text


def test_print_bar_enriches_scores_from_reasoning_logs(monkeypatch):
    """LLM contracts often omit composite; arbitration logs carry the scores."""
    monkeypatch.setenv("MODE", "backtest")
    monkeypatch.setenv("AIMM_BACKTEST_TERMINAL_LOG", "1")
    configure_backtest_terminal_logging()
    buf = io.StringIO()
    wf = {
        "profile_weights": {"2.3": 0.55, "1.1": 0.25},
        "tier0_contracts": [
            {
                "agent_id": "2.3",
                "label": "Technical TA Engine",
                "source": "agent_llm",
                "reasoning": "RSI at 51; MACD hist positive.",
            }
        ],
        "reasoning_logs": [
            {
                "node": "weighted_arbitrator",
                "extra": {"agent_id": "2.3"},
                "decision": {"composite": 0.57, "confidence": 0.64, "stance": "bullish"},
            }
        ],
        "arbitration_result": {"composite": 0.55, "confidence": 0.64, "stance": "bullish"},
    }
    print_bar_decision(
        bar_index=51,
        total_bars=60,
        symbol="BTC/USDT",
        close=62583.0,
        ts_ms=1_783_036_800_000,
        wf_output=wf,
        action="BUY",
        confidence=0.64,
        equity=10_000.0,
        stream=buf,
    )
    text = buf.getvalue()
    assert "comp  57/100" in text or "comp 57/100" in text
    assert "▲ bullish" in text
    assert "MACD hist" in text
    assert "desks neutral" in text or "TA-led" in text or "composite gates" in text


def test_terminal_log_disabled(monkeypatch):
    monkeypatch.setenv("MODE", "backtest")
    monkeypatch.setenv("AIMM_BACKTEST_TERMINAL_LOG", "0")
    buf = io.StringIO()
    print_run_summary(
        run_id="bt_test",
        metrics={"total_return_pct": 5.0, "sharpe": 1.1, "max_drawdown_pct": -3.0},
        trade_count=2,
        steps=10,
        stream=buf,
    )
    assert buf.getvalue() == ""


def test_quiet_library_loggers_even_when_cot_disabled(monkeypatch):
    """SDK/HTTP loggers stay muted when desk CoT is off."""
    from backtest.terminal_log import quiet_backtest_library_loggers

    monkeypatch.setenv("MODE", "backtest")
    monkeypatch.setenv("AIMM_BACKTEST_TERMINAL_LOG", "0")
    quiet_backtest_library_loggers()
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("workflow.weighted_arbitrator").level == logging.WARNING
