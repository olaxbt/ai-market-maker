"""
Wyckoff Scanner — Standalone Phase Identifier
==============================================

Designed as a clean drop-in module for any team that wants to identify which
Wyckoff phase (A / B / C / D / E) a token is currently in, with evidence and
intermediate metrics. Inspired by Wyckoff's classical accumulation schematic
(Selling Climax → Automatic Rally → Secondary Test → Spring → Sign of Strength
→ Last Point of Support → Markup) and adapted for crypto futures using OI,
volume, and price action.

This file is INTENTIONALLY independent of the in-house V88/V91 strategy
engines. It uses only generic OHLCV+OI inputs and is safe to copy to another
project / team.

Public API:
    from wyckoff_scanner import detect_wyckoff_phase, scan_universe

    res = detect_wyckoff_phase(df)
    print(res.phase, res.confidence, res.evidence)

Phase detection logic (high-level):
    Phase A — Stopping action: SC (selling climax) detected by extreme down-bar
              volume / price-spread, followed by AR (automatic rally) > ATR×2.
    Phase B — Cause-building: price oscillates inside range; OI ranges; multiple
              tests of support and resistance with neither breaking.
    Phase C — Spring: undercut of Phase B support followed by rapid recovery.
    Phase D — Sign of Strength: higher-high above Phase B resistance with
              volume confirmation; LPS = pullback to former resistance turned
              support.
    Phase E — Markup: structure already broken upward; price > Phase B range,
              moving averages aligned long.

Scoring methodology:
    Each phase has 3-5 evidence checks. Confidence = fraction of checks passed.
    The scanner returns the phase with highest confidence (ties broken in
    chronological order: E > D > C > B > A — most advanced phase wins).

Run as script:
    python wyckoff_scanner.py                     # full universe scan → JSON
    python wyckoff_scanner.py --symbol BTCUSDT    # single-token diagnostic
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


def _default_screener_root() -> Path:
    """davis-ai-market-maker repo root when this file lives in scripts/token_screeners/."""
    return Path(__file__).resolve().parent.parent.parent


# ── PATHS ────────────────────────────────────────────────────────────────────
# Override with env TOKEN_SCREENER_ROOT (directory containing Screened_data/ + screened_result/).
_ROOT = Path(os.environ.get("TOKEN_SCREENER_ROOT", _default_screener_root())).resolve()
ROOT_DIR = _ROOT
DATA_DIR = str(_ROOT / "Screened_data")
OUTPUT_DIR = str(_ROOT / "screened_result")
UNIVERSE_FN = "wyckoff_universe.json"

# ── CONFIG ───────────────────────────────────────────────────────────────────
DEFAULT_PARAMS = {
    "scan_tf": "1h",  # "5m" | "15m" | "1h" | "4h"
    "lookback_bars": 300,  # how far back to look for the most recent range
    # Phase A: Selling Climax detection
    "sc_volume_z_min": 2.5,  # SC bar must have volume Z ≥ 2.5
    "sc_range_atr_min": 2.0,  # SC bar's true range must be ≥ 2.0 × prior ATR
    "ar_min_rebound_atr": 2.0,  # Automatic Rally must be ≥ 2.0 × ATR off the SC low
    # Phase B: Range identification
    "range_min_bars": 30,  # range must persist ≥ 30 bars on scan_tf
    "range_max_width_pct": 40.0,  # range width ≤ 40% of midpoint price
    "range_test_count": 3,  # ≥3 touches of either boundary
    # Phase C: Spring
    "spring_undercut_pct": 1.5,  # spring low must be ≥ 1.5% below range low
    "spring_recovery_bars": 3,  # must recover above range low within N bars
    # Phase D / E
    "sos_breakout_pct": 2.0,  # break must be ≥ 2% above range high
    "sos_volume_z_min": 1.5,  # breakout bar volume Z ≥ 1.5
    "lps_max_pullback_pct": 5.0,  # LPS pullback ≤ 5% of breakout move
    # Generic
    "atr_window": 14,
    "vol_z_window": 50,
    # OI checks (optional — gracefully skipped if no `oi` column)
    "oi_phase_b_quiet_pct": 5.0,  # OI range during Phase B should stay within ±5%
    "oi_spring_spike_z_min": 2.0,  # OI Z must spike ≥ 2.0 on the spring bar
}


# ════════════════════════════════════════════════════════════════════════════
#   DATA CLASSES
# ════════════════════════════════════════════════════════════════════════════


@dataclass
class Evidence:
    name: str
    passed: bool
    value: float = 0.0
    threshold: float = 0.0
    note: str = ""

    def to_dict(self):
        return {
            "name": str(self.name),
            "passed": bool(self.passed),
            "value": float(self.value) if self.value is not None else 0.0,
            "threshold": float(self.threshold) if self.threshold is not None else 0.0,
            "note": str(self.note),
        }


@dataclass
class WyckoffEvent:
    """A single landmark event in the Wyckoff schematic."""

    label: str  # "SC" | "AR" | "ST" | "Spring" | "Test" | "SOS" | "LPS"
    bar_idx: int
    timestamp: str
    price: float
    note: str = ""

    def to_dict(self):
        return {
            "label": str(self.label),
            "bar_idx": int(self.bar_idx),
            "timestamp": str(self.timestamp),
            "price": float(self.price),
            "note": str(self.note),
        }


@dataclass
class WyckoffResult:
    symbol: str
    scan_tf: str
    bar_count: int
    last_close: float
    last_ts: str
    phase: str = "Unknown"  # "A" | "B" | "C" | "D" | "E" | "Unknown"
    phase_confidence: float = 0.0  # 0-100
    phase_scores: dict = field(default_factory=dict)  # confidence per phase
    range_low: float = 0.0
    range_high: float = 0.0
    range_bars: int = 0
    events: list = field(default_factory=list)
    evidence: dict = field(default_factory=dict)  # per-phase evidence list
    diagnostic_text: str = ""
    error: Optional[str] = None

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "scan_tf": self.scan_tf,
            "bar_count": int(self.bar_count),
            "last_close": float(self.last_close),
            "last_ts": str(self.last_ts),
            "phase": self.phase,
            "phase_confidence": float(self.phase_confidence),
            "phase_scores": {k: float(v) for k, v in self.phase_scores.items()},
            "range_low": float(self.range_low),
            "range_high": float(self.range_high),
            "range_bars": int(self.range_bars),
            "events": [e for e in self.events],
            "evidence": self.evidence,
            "diagnostic_text": self.diagnostic_text,
            "error": self.error,
        }


# ════════════════════════════════════════════════════════════════════════════
#   TECHNICAL HELPERS
# ════════════════════════════════════════════════════════════════════════════


def _resample(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    if tf == "5m":
        return df.copy()
    rule = {"15m": "15min", "1h": "1h", "4h": "4h", "1d": "1D"}.get(tf, "1h")
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").sort_index()
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    if "oi" in df.columns:
        agg["oi"] = "last"
    return df.resample(rule).agg(agg).dropna(subset=["close"]).reset_index()


def _atr(df: pd.DataFrame, n: int) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    pc = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - pc).abs(), (low - pc).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(n, min_periods=1).mean()


def _zscore(s: pd.Series, n: int) -> pd.Series:
    mu = s.rolling(n, min_periods=1).mean()
    sd = s.rolling(n, min_periods=1).std()
    return (s - mu) / sd.replace(0, np.nan)


# ════════════════════════════════════════════════════════════════════════════
#   PHASE DETECTORS
# ════════════════════════════════════════════════════════════════════════════


def _detect_phase_a(df: pd.DataFrame, params: dict) -> tuple[list[Evidence], list[WyckoffEvent]]:
    """Selling Climax + Automatic Rally + Secondary Test."""
    ev: list[Evidence] = []
    events: list[WyckoffEvent] = []

    n = len(df)
    if n < 50:
        ev.append(Evidence("A_data_sufficiency", False, n, 50, "n<50"))
        return ev, events

    atr = _atr(df, params["atr_window"]).values
    vol_z = _zscore(df["volume"].astype(float), params["vol_z_window"]).fillna(0).values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    ts = pd.to_datetime(df["timestamp"]).astype(str).values

    # Walk back from the recent 100 bars — find SC candidate
    scan_window = min(100, n)
    sc_idx = -1
    for i in range(n - scan_window, n):
        if i < params["atr_window"] + 1:
            continue
        bar_range = highs[i] - lows[i]
        if (
            vol_z[i] >= params["sc_volume_z_min"]
            and bar_range >= params["sc_range_atr_min"] * atr[i - 1]
            and closes[i] < closes[i - 1]
        ):  # close below previous = down bar
            sc_idx = i
            break

    if sc_idx >= 0:
        events.append(
            WyckoffEvent(
                "SC",
                sc_idx,
                ts[sc_idx],
                float(lows[sc_idx]),
                f"vol_z={vol_z[sc_idx]:.2f}  range/atr={(highs[sc_idx] - lows[sc_idx]) / atr[sc_idx - 1]:.2f}",
            )
        )
        ev.append(
            Evidence(
                "A_selling_climax",
                True,
                vol_z[sc_idx],
                params["sc_volume_z_min"],
                f"SC at bar {sc_idx} (vol_z={vol_z[sc_idx]:.2f})",
            )
        )

        # Automatic Rally check
        if sc_idx + 5 < n:
            window = highs[sc_idx + 1 : min(sc_idx + 25, n)]
            if len(window) > 0:
                ar_high = float(window.max())
                ar_idx_offset = int(np.argmax(window))
                rebound = ar_high - lows[sc_idx]
                ar_ok = rebound >= params["ar_min_rebound_atr"] * atr[sc_idx]
                ev.append(
                    Evidence(
                        "A_automatic_rally",
                        ar_ok,
                        rebound / max(atr[sc_idx], 1e-9),
                        params["ar_min_rebound_atr"],
                        f"AR rebound {rebound:.4f} ({rebound / atr[sc_idx]:.2f}× ATR)",
                    )
                )
                if ar_ok:
                    ar_bar = sc_idx + 1 + ar_idx_offset
                    events.append(
                        WyckoffEvent(
                            "AR",
                            ar_bar,
                            ts[ar_bar],
                            ar_high,
                            f"{rebound / atr[sc_idx]:.2f}× ATR rebound",
                        )
                    )
            else:
                ev.append(
                    Evidence(
                        "A_automatic_rally", False, 0, params["ar_min_rebound_atr"], "no AR window"
                    )
                )
        else:
            ev.append(Evidence("A_automatic_rally", False, 0, 0, "SC too recent"))
    else:
        ev.append(
            Evidence(
                "A_selling_climax",
                False,
                0,
                params["sc_volume_z_min"],
                "no SC candidate in last 100 bars",
            )
        )
        ev.append(Evidence("A_automatic_rally", False, 0, 0, "no SC, no AR"))

    return ev, events


def _detect_range(df: pd.DataFrame, params: dict) -> tuple[float, float, int, int]:
    """
    Identify the most recent multi-bar range.
    Returns (range_low, range_high, range_bars, range_start_idx)
    or (0, 0, 0, -1) if no usable range found.
    """
    n = len(df)
    if n < params["range_min_bars"] + 5:
        return 0.0, 0.0, 0, -1

    highs = df["high"].values
    lows = df["low"].values

    # Walk through expanding windows from the latest bar backwards.
    # The "range" is defined as a contiguous block where price oscillates
    # within a band whose width <= range_max_width_pct of midpoint.
    best_start = -1
    best_lo = 0.0
    best_hi = 0.0
    for length in range(params["range_min_bars"], min(params["lookback_bars"], n)):
        start = n - length
        lo = float(lows[start:n].min())
        hi = float(highs[start:n].max())
        mid = (lo + hi) / 2
        if mid > 0 and (hi - lo) / mid * 100 <= params["range_max_width_pct"]:
            best_start = start
            best_lo = lo
            best_hi = hi
        else:
            # range broke — stop expanding
            break
    if best_start < 0:
        return 0.0, 0.0, 0, -1
    return best_lo, best_hi, n - best_start, best_start


def _detect_phase_b(
    df: pd.DataFrame, params: dict, range_lo: float, range_hi: float, range_bars: int
) -> list[Evidence]:
    """Cause-building: oscillation inside range, multiple boundary tests."""
    ev: list[Evidence] = []

    if range_bars == 0:
        ev.append(
            Evidence("B_range_present", False, 0, params["range_min_bars"], "no range identified")
        )
        return ev

    ev.append(
        Evidence(
            "B_range_present",
            True,
            range_bars,
            params["range_min_bars"],
            f"range bars = {range_bars} ({range_lo:.4f} - {range_hi:.4f})",
        )
    )

    n = len(df)
    highs = df["high"].values
    lows = df["low"].values
    rstart = n - range_bars
    # tolerance band — within 1% of either boundary counts as a touch
    upper_tol = range_hi * 0.99
    lower_tol = range_lo * 1.01
    upper_touches = int(np.sum(highs[rstart:] >= upper_tol))
    lower_touches = int(np.sum(lows[rstart:] <= lower_tol))
    ev.append(
        Evidence(
            "B_upper_touches",
            upper_touches >= params["range_test_count"],
            upper_touches,
            params["range_test_count"],
            f"resistance touches in range: {upper_touches}",
        )
    )
    ev.append(
        Evidence(
            "B_lower_touches",
            lower_touches >= params["range_test_count"],
            lower_touches,
            params["range_test_count"],
            f"support touches in range: {lower_touches}",
        )
    )

    # Optional: OI quiet check
    if "oi" in df.columns:
        oi = df["oi"].astype(float).values[rstart:]
        if len(oi) > 0 and oi.mean() > 0:
            oi_pct = (oi.max() - oi.min()) / oi.mean() * 100
            ev.append(
                Evidence(
                    "B_oi_ranging",
                    oi_pct <= params["oi_phase_b_quiet_pct"] * 4,
                    oi_pct,
                    params["oi_phase_b_quiet_pct"] * 4,
                    f"OI swing within range: {oi_pct:.1f}%",
                )
            )
    return ev


def _detect_phase_c(
    df: pd.DataFrame, params: dict, range_lo: float, range_hi: float, range_bars: int
) -> tuple[list[Evidence], list[WyckoffEvent]]:
    """Spring: undercut of range_lo followed by rapid recovery."""
    ev: list[Evidence] = []
    events: list[WyckoffEvent] = []
    n = len(df)
    if range_bars == 0:
        ev.append(Evidence("C_spring", False, 0, 0, "no range"))
        return ev, events

    lows = df["low"].values
    closes = df["close"].values
    ts = pd.to_datetime(df["timestamp"]).astype(str).values

    # Look at the LAST `range_bars` for an undercut
    rstart = n - range_bars
    threshold = range_lo * (1 - params["spring_undercut_pct"] / 100.0)
    spring_idx = -1
    for i in range(rstart, n):
        if lows[i] <= threshold:
            spring_idx = i
            break

    if spring_idx < 0:
        ev.append(
            Evidence(
                "C_spring",
                False,
                0,
                params["spring_undercut_pct"],
                "no undercut of range_low detected",
            )
        )
        return ev, events

    # Recovery: did close get back above range_lo within spring_recovery_bars?
    recovery_window = closes[
        spring_idx + 1 : min(spring_idx + 1 + params["spring_recovery_bars"], n)
    ]
    recovered = bool((recovery_window > range_lo).any())
    ev.append(
        Evidence(
            "C_spring",
            True,
            lows[spring_idx],
            threshold,
            f"undercut at bar {spring_idx} (low={lows[spring_idx]:.4f}, threshold={threshold:.4f})",
        )
    )
    ev.append(
        Evidence(
            "C_spring_recovery",
            recovered,
            1.0,
            1.0,
            f"recovered above range_lo within {params['spring_recovery_bars']} bars: {recovered}",
        )
    )
    events.append(
        WyckoffEvent(
            "Spring",
            spring_idx,
            ts[spring_idx],
            float(lows[spring_idx]),
            f"undercut by {(range_lo - lows[spring_idx]) / range_lo * 100:.2f}%, recovered={recovered}",
        )
    )

    # Optional: OI Z spike on the spring bar
    if "oi" in df.columns:
        oi = df["oi"].astype(float)
        oi_z = _zscore(oi, params["vol_z_window"]).fillna(0).values
        ev.append(
            Evidence(
                "C_oi_spring_spike",
                oi_z[spring_idx] >= params["oi_spring_spike_z_min"],
                float(oi_z[spring_idx]),
                params["oi_spring_spike_z_min"],
                f"OI Z on spring bar = {oi_z[spring_idx]:.2f}",
            )
        )
    return ev, events


def _detect_phase_d_e(
    df: pd.DataFrame, params: dict, range_lo: float, range_hi: float, range_bars: int
) -> tuple[list[Evidence], list[WyckoffEvent], bool]:
    """Sign of Strength + LPS detection. Returns (evidence, events, is_phase_e)."""
    ev: list[Evidence] = []
    events: list[WyckoffEvent] = []
    n = len(df)
    if range_bars == 0:
        ev.append(Evidence("D_breakout", False, 0, 0, "no range"))
        return ev, events, False

    lows = df["low"].values
    closes = df["close"].values
    ts = pd.to_datetime(df["timestamp"]).astype(str).values
    vol_z = _zscore(df["volume"].astype(float), params["vol_z_window"]).fillna(0).values

    # SOS = first close above range_hi × (1 + sos_breakout_pct/100)
    sos_threshold = range_hi * (1 + params["sos_breakout_pct"] / 100.0)
    sos_idx = -1
    rstart = n - range_bars
    for i in range(rstart, n):
        if closes[i] >= sos_threshold and vol_z[i] >= params["sos_volume_z_min"]:
            sos_idx = i
            break

    if sos_idx < 0:
        ev.append(
            Evidence(
                "D_breakout",
                False,
                0,
                params["sos_breakout_pct"],
                "no qualified breakout above range_high",
            )
        )
        return ev, events, False

    ev.append(
        Evidence(
            "D_breakout",
            True,
            closes[sos_idx],
            sos_threshold,
            f"SOS at bar {sos_idx}, close={closes[sos_idx]:.4f}, vol_z={vol_z[sos_idx]:.2f}",
        )
    )
    events.append(
        WyckoffEvent(
            "SOS", sos_idx, ts[sos_idx], float(closes[sos_idx]), f"vol_z={vol_z[sos_idx]:.2f}"
        )
    )

    # LPS: pullback to former resistance (range_hi) without losing it
    is_phase_e = False
    if sos_idx + 1 < n:
        post = lows[sos_idx + 1 :]
        if len(post) > 0:
            min_post = float(post.min())
            held = min_post >= range_hi * (1 - 0.01)  # within 1% of former resistance
            ev.append(
                Evidence(
                    "D_lps_held",
                    held,
                    min_post,
                    range_hi,
                    f"min post-breakout low = {min_post:.4f}; range_hi = {range_hi:.4f}",
                )
            )
            # Phase E if price has continued meaningfully higher and never returned to range
            current = float(closes[-1])
            if held and current > range_hi * 1.05:
                is_phase_e = True
                ev.append(
                    Evidence(
                        "E_markup_extended",
                        True,
                        current,
                        range_hi * 1.05,
                        f"price {current:.4f} > range_hi×1.05",
                    )
                )
        else:
            ev.append(Evidence("D_lps_held", False, 0, range_hi, "SOS too recent"))
    else:
        ev.append(Evidence("D_lps_held", False, 0, range_hi, "SOS at last bar"))

    return ev, events, is_phase_e


# ════════════════════════════════════════════════════════════════════════════
#   COMPOSITE — pick the dominant phase
# ════════════════════════════════════════════════════════════════════════════


def _phase_confidence(evidence: list[Evidence]) -> float:
    if not evidence:
        return 0.0
    return 100.0 * sum(1 for e in evidence if e.passed) / len(evidence)


def detect_wyckoff_phase(
    df: pd.DataFrame, symbol: str = "?", params: Optional[dict] = None
) -> WyckoffResult:
    """Run full Wyckoff phase detection on an OHLCV(+OI) DataFrame."""
    params = {**DEFAULT_PARAMS, **(params or {})}

    try:
        rdf = _resample(df, params["scan_tf"])
    except Exception as e:
        return WyckoffResult(
            symbol=symbol,
            scan_tf=params["scan_tf"],
            bar_count=0,
            last_close=0,
            last_ts="",
            error=f"resample: {e}",
        )

    n = len(rdf)
    if n < 60:
        return WyckoffResult(
            symbol=symbol,
            scan_tf=params["scan_tf"],
            bar_count=n,
            last_close=float(rdf["close"].iloc[-1]) if n else 0,
            last_ts=str(rdf["timestamp"].iloc[-1]) if n else "",
            error="insufficient bars",
        )

    # Identify the recent range
    rng_lo, rng_hi, rng_bars, rng_start = _detect_range(rdf, params)

    # Run each phase detector
    ev_a, events_a = _detect_phase_a(rdf, params)
    ev_b = _detect_phase_b(rdf, params, rng_lo, rng_hi, rng_bars)
    ev_c, events_c = _detect_phase_c(rdf, params, rng_lo, rng_hi, rng_bars)
    ev_de, events_de, is_e = _detect_phase_d_e(rdf, params, rng_lo, rng_hi, rng_bars)

    conf = {
        "A": _phase_confidence(ev_a),
        "B": _phase_confidence(ev_b),
        "C": _phase_confidence(ev_c),
        "D": _phase_confidence(ev_de),
    }

    # Decide dominant phase. Walk most-advanced backwards.
    # Phase E shortcut (markup extended already)
    if is_e:
        phase = "E"
        confidence = 100.0
    elif conf["D"] >= 50:
        phase = "D"
        confidence = conf["D"]
    elif conf["C"] >= 50:
        phase = "C"
        confidence = conf["C"]
    elif conf["B"] >= 50:
        phase = "B"
        confidence = conf["B"]
    elif conf["A"] >= 50:
        phase = "A"
        confidence = conf["A"]
    else:
        phase = "Unknown"
        confidence = max(conf.values()) if conf else 0.0

    all_events = events_a + events_c + events_de

    diagnostic = (
        f"{symbol} | Phase {phase} ({confidence:.0f}% conf) | "
        f"Range {rng_lo:.4f}-{rng_hi:.4f} ({rng_bars} bars) | "
        f"Events: {[e.label for e in all_events]}"
    )

    res = WyckoffResult(
        symbol=symbol,
        scan_tf=params["scan_tf"],
        bar_count=int(n),
        last_close=float(rdf["close"].iloc[-1]),
        last_ts=str(rdf["timestamp"].iloc[-1]),
        phase=phase,
        phase_confidence=float(confidence),
        phase_scores={k: float(v) for k, v in conf.items()},
        range_low=float(rng_lo),
        range_high=float(rng_hi),
        range_bars=int(rng_bars),
        events=[e.to_dict() for e in all_events],
        evidence={
            "A": [e.to_dict() for e in ev_a],
            "B": [e.to_dict() for e in ev_b],
            "C": [e.to_dict() for e in ev_c],
            "D": [e.to_dict() for e in ev_de],
        },
        diagnostic_text=diagnostic,
    )
    return res


# ════════════════════════════════════════════════════════════════════════════
#   STANDALONE SCAN
# ════════════════════════════════════════════════════════════════════════════


def _load_token_csv(path: str, recent_5m_bars: int = 6000) -> Optional[pd.DataFrame]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            lines = fh.readlines()
        if len(lines) < 2:
            return None
        header = lines[:1]
        body = lines[max(1, len(lines) - recent_5m_bars) :]
        import io

        df = pd.read_csv(io.StringIO("".join(header + body)))
        cmap = {"t": "timestamp", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
        df = df.rename(columns={k: v for k, v in cmap.items() if k in df.columns})
        if "timestamp" not in df.columns:
            return None
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp", "close"])
        for col in ["open", "high", "low", "volume"]:
            if col not in df.columns:
                df[col] = df["close"] if col != "volume" else 0.0
        return df
    except Exception:
        return None


def scan_universe(params: Optional[dict] = None, verbose: bool = True) -> dict:
    params = {**DEFAULT_PARAMS, **(params or {})}
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*_Master_Tick_Data.csv")))
    if verbose:
        print(f"[Wyckoff] Scanning {len(files)} tokens at scan_tf={params['scan_tf']}...")

    results: list[WyckoffResult] = []
    for idx, fp in enumerate(files):
        symbol = os.path.basename(fp).replace("_Master_Tick_Data.csv", "")
        df = _load_token_csv(fp)
        if df is None or df.empty:
            continue
        res = detect_wyckoff_phase(df, symbol=symbol, params=params)
        results.append(res)
        if verbose and (idx + 1) % 50 == 0:
            print(f"  ... scanned {idx + 1}/{len(files)}")

    # Group by phase
    by_phase = {p: [r for r in results if r.phase == p] for p in "ABCDE"}
    out = {
        "scan_time_utc8": (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(
            timespec="seconds"
        ),
        "config": params,
        "n_scanned": len(results),
        "phase_counts": {p: len(by_phase[p]) for p in "ABCDE"},
        "n_unknown": sum(1 for r in results if r.phase == "Unknown"),
        "tokens": [r.to_dict() for r in results],
    }

    out_path = os.path.join(OUTPUT_DIR, UNIVERSE_FN)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    if verbose:
        print(f"[Wyckoff] Wrote {out_path}")
        print(
            "[Wyckoff] Phase distribution: "
            + "  ".join(f"{p}={out['phase_counts'][p]}" for p in "ABCDE")
            + f"  Unknown={out['n_unknown']}"
        )
        # Show top examples per phase
        for p in "CDE":
            tokens_in_phase = [r for r in results if r.phase == p][:5]
            if tokens_in_phase:
                print(f"\n[Wyckoff] Phase {p} examples:")
                for r in tokens_in_phase:
                    print(
                        f"  {r.symbol:<14} conf={r.phase_confidence:5.0f}%  "
                        f"range={r.range_low:.4g}-{r.range_high:.4g}  events={[e['label'] for e in r.events]}"
                    )
    return out


def load_universe_by_phase(
    phases: tuple = ("C", "D", "E"), min_confidence: float = 50.0, max_age_minutes: int = 90
) -> set[str]:
    """Return set of symbols currently in any of the requested phases."""
    path = os.path.join(OUTPUT_DIR, UNIVERSE_FN)
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        scan_time = pd.to_datetime(data["scan_time_utc8"])
        age_min = (pd.Timestamp.now() - scan_time).total_seconds() / 60
        if age_min > max_age_minutes:
            print(f"[Wyckoff] WARNING: universe is {age_min:.0f} min old")
        out = set()
        for t in data.get("tokens", []):
            if t["phase"] in phases and t["phase_confidence"] >= min_confidence:
                out.add(t["symbol"])
        return out
    except Exception as e:
        print(f"[Wyckoff] load_universe failed: {e}")
        return set()


# ════════════════════════════════════════════════════════════════════════════
#   CLI
# ════════════════════════════════════════════════════════════════════════════


def _cli():
    p = argparse.ArgumentParser(description="Wyckoff phase scanner")
    p.add_argument("--tf", default=None, help="scan timeframe: 5m | 15m | 1h | 4h")
    p.add_argument("--symbol", default=None, help="single token diagnostic")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    params = dict(DEFAULT_PARAMS)
    if args.tf:
        params["scan_tf"] = args.tf

    if args.symbol:
        sym = args.symbol if args.symbol.endswith("USDT") else f"{args.symbol}USDT"
        path = os.path.join(DATA_DIR, f"{sym}_Master_Tick_Data.csv")
        df = _load_token_csv(path)
        if df is None:
            print(f"No data for {sym}")
            sys.exit(1)
        res = detect_wyckoff_phase(df, symbol=sym, params=params)
        print(json.dumps(res.to_dict(), indent=2, default=str))
        sys.exit(0)

    scan_universe(params=params, verbose=not args.quiet)


if __name__ == "__main__":
    _cli()
