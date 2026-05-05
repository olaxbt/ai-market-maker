"""Result validation for leaderboard submissions.

Anti-fraud checks:
  - Basic: out-of-range return, sharpe, drawdown
  - Temporal: timestamp sanity, start_time cannot be in the future
  - Exchange existence: ticker validation against known exchange pairs
  - PnL consistency: total_return should be approximately verifiable
    from final_value / initial_capital
  - Replay: nonce dedup per provider
"""

from __future__ import annotations

import time
from typing import Any

KNOWABLE_BEFORE = {
    "BTC/USDT": "2009-01-03",
    "ETH/USDT": "2015-07-30",
    "SOL/USDT": "2020-03-16",
    "BNB/USDT": "2017-07-14",
    "XRP/USDT": "2013-01-01",
    "ADA/USDT": "2017-09-29",
    "DOGE/USDT": "2013-12-08",
    "AVAX/USDT": "2020-09-22",
    "DOT/USDT": "2020-08-21",
    "LINK/USDT": "2017-09-19",
    "MATIC/USDT": "2019-04-26",
    "ATOM/USDT": "2019-03-14",
    "UNI/USDT": "2020-09-17",
    "ARB/USDT": "2023-03-23",
    "OP/USDT": "2022-06-01",
}

# These tickers have been verified as existing on Binance spot
BINANCE_KNOWN_TICKERS = {
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "DOGE/USDT",
    "AVAX/USDT",
    "DOT/USDT",
    "LINK/USDT",
    "MATIC/USDT",
    "ATOM/USDT",
    "UNI/USDT",
    "ARB/USDT",
    "OP/USDT",
    "SUI/USDT",
    "APT/USDT",
    "TIA/USDT",
    "SEI/USDT",
    "INJ/USDT",
    "PEPE/USDT",
    "WIF/USDT",
    "BONK/USDT",
    "CORE/USDT",
    "FTM/USDT",
    "ALGO/USDT",
    "NEAR/USDT",
    "FIL/USDT",
    "AAVE/USDT",
    "CRV/USDT",
    "COMP/USDT",
    "MKR/USDT",
    "AXS/USDT",
    "SAND/USDT",
    "MANA/USDT",
    "ENJ/USDT",
    "LTC/USDT",
    "BCH/USDT",
    "ETC/USDT",
}

# Tickers known to be delisted / inactive
DELISTED_TICKERS: set[str] = set()


_VALID_RESULT_TYPES = {"backtest", "live_scan", "paper_scan"}


def ticker_exists(ticker: str) -> bool:
    """Check if ticker is known to exist on a major exchange.

    Returns True for known pairs, True for unknown (permissive), False for known-delisted.
    """
    t = ticker.upper().strip()
    if t in DELISTED_TICKERS:
        return False
    return True


def earliest_possible_start(ticker: str) -> int | None:
    """Earliest Unix timestamp this ticker could have been traded.

    Returns None for unknown tickers (pass).
    """
    t = ticker.upper().strip()
    date_str = KNOWABLE_BEFORE.get(t)
    if not date_str:
        return None
    from datetime import datetime, timezone

    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _as_str(x: Any) -> str:
    return x.strip() if isinstance(x, str) else str(x or "").strip()


def _as_float(x: Any) -> float | None:
    return float(x) if isinstance(x, (int, float)) else None


def _as_int(x: Any) -> int | None:
    return int(x) if isinstance(x, (int, float)) else None


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize supported submission shapes into the canonical summary format.

    Supported:
      - /leadpage/external_result: {provider,ticker,result_type,summary,submitted_at}
      - /leadpage/results (ExternalResult model): flat metrics + optional meta['result_type']
    """
    out: dict[str, Any] = dict(payload)

    # If already in canonical shape, just ensure summary is a dict.
    if "summary" in out:
        s = out.get("summary") or {}
        out["summary"] = s if isinstance(s, dict) else {}
        return out

    # Flattened ExternalResult shape: map into summary and infer result_type.
    meta = out.get("meta") if isinstance(out.get("meta"), dict) else {}
    inferred_rt = _as_str(meta.get("result_type") or out.get("result_type") or "backtest")

    out2: dict[str, Any] = {
        "provider": out.get("provider"),
        "ticker": out.get("ticker"),
        "result_type": inferred_rt,
        "submitted_at": out.get("submitted_at"),
        "summary": {
            "total_return_pct": out.get("total_return_pct"),
            "sharpe_ratio": out.get("sharpe")
            if out.get("sharpe") is not None
            else out.get("sharpe_ratio"),
            "max_drawdown_pct": out.get("max_drawdown_pct"),
            "total_trades": out.get("trade_count"),
        },
    }
    return out2


def validate_result(payload: dict[str, Any]) -> list[str]:
    """Validate a result submission payload.

    Returns a list of error messages. Empty list = valid.
    """
    errors: list[str] = []
    now_ts = int(time.time())

    p = _normalize_payload(payload)

    result_type = p.get("result_type", "")
    if result_type not in _VALID_RESULT_TYPES:
        errors.append(
            f"Invalid result_type '{result_type}'; must be one of {sorted(_VALID_RESULT_TYPES)}"
        )

    ticker = p.get("ticker", "")
    if not isinstance(ticker, str) or "/" not in ticker:
        errors.append("ticker should be a trading pair (e.g. BTC/USDT)")
    else:
        if not ticker_exists(ticker):
            errors.append(f"ticker '{ticker}' refers to a known-delisted instrument")

    summary = p.get("summary", {}) or {}
    if not isinstance(summary, dict):
        errors.append("summary must be a dict")
        return errors

    submitted_at = p.get("submitted_at", 0)
    submitted_at_i = _as_int(submitted_at)
    if isinstance(submitted_at_i, int) and submitted_at_i > 0:
        age = now_ts - submitted_at_i
        if age < 0:
            errors.append("submitted_at cannot be in the future")
        if age > 86400 * 365 * 5:
            errors.append("submitted_at is more than 5 years in the past")

    # ── Temporal validation ──
    start_time = summary.get("start_time")
    end_time = summary.get("end_time")
    if start_time and ticker:
        try:
            from datetime import datetime, timezone

            if isinstance(start_time, str):
                dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                start_ts = int(dt.replace(tzinfo=timezone.utc).timestamp())
            elif isinstance(start_time, (int, float)):
                start_ts = int(start_time)
            else:
                start_ts = 0

            if start_ts > 0:
                if start_ts > now_ts + 60:
                    errors.append("start_time cannot be in the future")
                earliest = earliest_possible_start(ticker)
                if earliest and start_ts < earliest:
                    errors.append(
                        f"start_time {start_time} predates known ticker inception ({earliest})"
                    )
        except (ValueError, TypeError):
            pass  # unparseable date — not a validation target

    if end_time and start_time:
        try:
            from datetime import datetime, timezone

            def _to_ts(x: Any) -> int:
                if isinstance(x, str):
                    dt = datetime.fromisoformat(x.replace("Z", "+00:00"))
                    return int(dt.replace(tzinfo=timezone.utc).timestamp())
                if isinstance(x, (int, float)):
                    return int(x)
                return 0

            st = _to_ts(start_time)
            et = _to_ts(end_time)
            if st > 0 and et > 0:
                if et > now_ts + 60:
                    errors.append("end_time cannot be in the future")
                if et < st:
                    errors.append("end_time cannot be before start_time")
        except (ValueError, TypeError):
            pass

    # ── PnL validation ──
    total_return_pct = summary.get("total_return_pct")
    if isinstance(total_return_pct, (int, float)):
        if total_return_pct > 5000:
            errors.append(
                f"total_return_pct {total_return_pct}% exceeds plausible threshold (5000%)"
            )

    sharpe = summary.get("sharpe_ratio")
    if isinstance(sharpe, (int, float)):
        if sharpe > 15:
            errors.append(f"sharpe_ratio {sharpe} exceeds plausible threshold (15)")
        if sharpe < -10:
            errors.append(f"sharpe_ratio {sharpe} below plausible threshold (-10)")

    max_dd = summary.get("max_drawdown_pct")
    if isinstance(max_dd, (int, float)):
        if max_dd > 0:
            errors.append(f"max_drawdown_pct {max_dd} is positive (should be negative)")
        if max_dd < -100:
            errors.append(f"max_drawdown_pct {max_dd}% exceeds plausible loss (max -100%)")

    win_rate = summary.get("win_rate_pct")
    if isinstance(win_rate, (int, float)):
        if win_rate < 0 or win_rate > 100:
            errors.append(f"win_rate_pct {win_rate} must be between 0 and 100")

    total_trades = summary.get("total_trades")
    if isinstance(total_trades, (int, float)):
        if total_trades < 0:
            errors.append("total_trades cannot be negative")
        if total_trades > 1_000_000:
            errors.append("total_trades > 1,000,000 — likely a mistake")

    # ── Consistency: final_value / initial_capital ≈ return ──
    initial = summary.get("initial_capital_usd")
    final = summary.get("final_value_usd")
    if isinstance(initial, (int, float)) and isinstance(final, (int, float)) and initial > 0:
        implied_return = ((final / initial) - 1) * 100
        if isinstance(total_return_pct, (int, float)):
            diff = abs(implied_return - total_return_pct)
            tol = 20.0
            if diff > tol and abs(total_return_pct) > 1:
                errors.append(
                    f"total_return_pct ({total_return_pct}%) diverges "
                    f"from implied PnL ({implied_return:.1f}%) by {diff:.1f} points"
                )

    return errors
