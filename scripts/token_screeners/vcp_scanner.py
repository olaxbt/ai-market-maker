"""
VCP Scanner — Volatility Contraction Pattern detector for crypto futures
=========================================================================

Implements Mark Minervini's Trend Template + VCP base detection, adapted for
crypto perpetuals. Designed to be:

1.  IMPORTABLE     — `from vcp_scanner import detect_vcp` returns a rich dict
                     with every gate's pass/fail and intermediate metrics, so
                     downstream code can choose its own strictness.
2.  STANDALONE     — running this file directly scans every CSV in
                     `Screened_data/` and writes `screened_result/vcp_universe.json`
                     for downstream strategies (v88_vcp.py, v91_vcp.py) and the
                     dashboard's Token Strategy Map.
3.  PURELY ADDITIVE — does NOT touch V88, V91, or any existing engine.

Output schema (vcp_universe.json):
    {
      "scan_time_utc8": "2026-05-09T00:15:00",
      "config": { ...constants used... },
      "tokens": [
          {
            "symbol": "ASSETUSDT",
            "vcp_score": 0..100,                 ← composite quality score
            "passed_strict": true/false,         ← all gates green
            "passed_relaxed": true/false,        ← Trend Template OK + ≥2 contractions
            "trend_template": { 8 sub-gates },
            "base": { contractions, dryup, tightness, pivot, distance_to_pivot },
            "diagnostic_text": "human-readable summary"
          },
          ...
      ]
    }

Usage:
    python vcp_scanner.py                # full scan, writes JSON
    python vcp_scanner.py --tf 1h        # use 1h bars instead of 4h
    python vcp_scanner.py --symbol BTCUSDT  # one token only, prints diagnostic
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from dataclasses import asdict, dataclass, field
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
UNIVERSE_FN = "vcp_universe.json"

# ── CONFIG ───────────────────────────────────────────────────────────────────
# All thresholds documented inline. Tunable per-timeframe via DEFAULT_PARAMS.
DEFAULT_PARAMS = {
    # ── Resampling target ─────────────────────────────────────────────────
    # The Master_Tick_Data files are 5m. VCP is a multi-bar structural pattern,
    # so we resample up to 1h (or 4h) before scanning. Crypto moves faster than
    # equities, so 1h ≈ daily-equivalent for swing-style VCPs.
    "scan_tf": "1h",  # "1h" | "4h" | "5m"
    # ── Trend Template (Minervini 8-rule "Stage 2" filter) ────────────────
    "ma_50": 50,
    "ma_150": 150,
    "ma_200": 200,
    "ma200_uptrend_window": 100,  # 200-MA must be ≥ value 100 bars ago (≈4 mo on 1h)
    "min_above_low_pct": 30,  # price must be ≥ 30% above 200-bar low
    "max_below_high_pct": 25,  # price must be within 25% of 200-bar high
    "rs_lookback": 120,  # bars used to compare token return vs BTC return
    "rs_rank_min": 60,  # token must beat ≥60% of return-percentile vs BTC
    # (equity uses 70 vs S&P; we soften slightly because
    # crypto correlations make RS noisier)
    # ── Base / contraction detection ──────────────────────────────────────
    "swing_strength": 3,  # bars to either side for pivot-high/low confirmation
    "base_lookback": 80,  # how many bars back to scan for the most recent base
    "min_contractions": 2,  # must find ≥2 successive pullbacks
    "ideal_contractions": 3,  # 3+ earns full structural-quality points
    "max_first_pullback": 35.0,  # first pullback allowed up to 35% (crypto runs deeper)
    "decay_ratio_max": 0.60,  # each pullback ≤ 60% of the previous (tighter = better)
    "min_total_decay": 0.50,  # last pullback must be ≤ 50% of the FIRST (tightest)
    # ── Volume dry-up ─────────────────────────────────────────────────────
    "vol_dryup_ratio_max": 0.75,  # avg vol in last contraction ≤ 75% of prior contraction
    "vol_dryup_window": 5,  # bars averaged on each contraction's volume
    # ── Tightness (final base) ────────────────────────────────────────────
    "tight_atr_window": 10,  # ATR window for tightness check
    "tight_pct_rank_max": 35,  # ATR/price must be ≤ 35th percentile of last 100 bars
    "tight_pct_rank_window": 100,
    # ── Pivot proximity (entry trigger zone) ──────────────────────────────
    "pivot_lookback": 20,  # pivot = highest high of last N bars
    "pivot_proximity_pct": 5.0,  # price must be within 5% below pivot to be "loaded"
    # ── Output gating ─────────────────────────────────────────────────────
    "strict_score_min": 75,  # passed_strict requires composite ≥ 75
    "relaxed_score_min": 50,  # passed_relaxed requires composite ≥ 50
}


# ════════════════════════════════════════════════════════════════════════════
#   DATA CLASSES — every gate's output is structured, never bare booleans
# ════════════════════════════════════════════════════════════════════════════


@dataclass
class GateResult:
    name: str
    passed: bool
    value: float = 0.0
    threshold: float = 0.0
    note: str = ""

    def to_dict(self):
        # Force native python types — numpy.bool_, numpy.float64 leak into JSON otherwise
        return {
            "name": str(self.name),
            "passed": bool(self.passed),
            "value": float(self.value) if self.value is not None else 0.0,
            "threshold": float(self.threshold) if self.threshold is not None else 0.0,
            "note": str(self.note),
        }


@dataclass
class Contraction:
    """One pullback inside the base — from a pivot high to the next pivot low."""

    high_idx: int
    high_ts: str
    high_px: float
    low_idx: int
    low_ts: str
    low_px: float
    depth_pct: float  # (high - low) / high * 100
    duration_bars: int
    avg_volume: float

    def to_dict(self):
        return asdict(self)


@dataclass
class VCPResult:
    symbol: str
    scan_tf: str
    bar_count: int
    last_close: float
    last_ts: str
    # ── gate groups
    trend_template: list = field(default_factory=list)
    base: list = field(default_factory=list)
    contractions: list = field(default_factory=list)
    pivot_price: float = 0.0
    distance_to_pivot_pct: float = 0.0
    # ── scoring
    vcp_score: float = 0.0
    passed_strict: bool = False
    passed_relaxed: bool = False
    diagnostic_text: str = ""
    error: Optional[str] = None

    def to_dict(self):
        d = asdict(self)
        d["trend_template"] = [g for g in d["trend_template"]]
        d["base"] = [g for g in d["base"]]
        return d


# ════════════════════════════════════════════════════════════════════════════
#   HELPERS
# ════════════════════════════════════════════════════════════════════════════


def _resample(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Resample 5m OHLCV to a coarser TF. Uses pandas resample with proper agg."""
    if tf == "5m":
        return df.copy()
    rule_map = {"15m": "15min", "1h": "1h", "4h": "4h", "1d": "1D"}
    rule = rule_map.get(tf, "1h")
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").sort_index()
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    if "oi" in df.columns:
        agg["oi"] = "last"
    out = df.resample(rule).agg(agg).dropna(subset=["close"]).reset_index()
    return out


def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    pc = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - pc).abs(), (low - pc).abs()],
        axis=1,
    ).max(axis=1)
    return tr.rolling(n, min_periods=1).mean()


def _find_pivot_highs(highs: np.ndarray, k: int) -> list[int]:
    """Pivot-high indices: bar i where high[i] >= max(highs[i-k:i+k+1])."""
    out = []
    for i in range(k, len(highs) - k):
        window = highs[i - k : i + k + 1]
        if highs[i] == window.max() and (highs[i] > highs[i - k] or highs[i] > highs[i + k]):
            out.append(i)
    return out


def _find_pivot_lows(lows: np.ndarray, k: int) -> list[int]:
    out = []
    for i in range(k, len(lows) - k):
        window = lows[i - k : i + k + 1]
        if lows[i] == window.min() and (lows[i] < lows[i - k] or lows[i] < lows[i + k]):
            out.append(i)
    return out


def _percentile_rank(series: pd.Series, value: float) -> float:
    """Where does `value` rank within `series` (0=lowest, 100=highest)?"""
    if len(series) == 0:
        return 50.0
    return float((series < value).mean() * 100)


# ════════════════════════════════════════════════════════════════════════════
#   GATE 1 — TREND TEMPLATE (Minervini 8-rule Stage 2 filter)
# ════════════════════════════════════════════════════════════════════════════


def evaluate_trend_template(
    df: pd.DataFrame, params: dict, btc_df: Optional[pd.DataFrame] = None
) -> list[GateResult]:
    """Returns 8 GateResult objects, one per Minervini rule."""
    out: list[GateResult] = []
    n = len(df)
    if n < params["ma_200"] + 10:
        return [
            GateResult(
                "data_sufficiency",
                False,
                n,
                params["ma_200"] + 10,
                "insufficient bars for 200-MA + history",
            )
        ]

    close = df["close"].astype(float).values
    ma50 = pd.Series(close).rolling(params["ma_50"]).mean().iloc[-1]
    ma150 = pd.Series(close).rolling(params["ma_150"]).mean().iloc[-1]
    ma200 = pd.Series(close).rolling(params["ma_200"]).mean().iloc[-1]
    px = close[-1]

    # TT-1: price > 150-MA AND > 200-MA
    out.append(
        GateResult(
            "TT1_price_above_150_and_200",
            passed=(px > ma150 and px > ma200),
            value=px,
            threshold=max(ma150, ma200),
            note=f"px={px:.4f}  ma150={ma150:.4f}  ma200={ma200:.4f}",
        )
    )

    # TT-2: 150-MA > 200-MA
    out.append(
        GateResult(
            "TT2_150ma_above_200ma",
            passed=(ma150 > ma200),
            value=ma150,
            threshold=ma200,
            note=f"ma150-ma200 = {ma150 - ma200:+.4f}",
        )
    )

    # TT-3: 200-MA in uptrend (current value > value k bars ago)
    k = params["ma200_uptrend_window"]
    if n > params["ma_200"] + k:
        ma200_old = pd.Series(close).rolling(params["ma_200"]).mean().iloc[-k]
        out.append(
            GateResult(
                "TT3_200ma_uptrend",
                passed=(ma200 > ma200_old),
                value=ma200,
                threshold=ma200_old,
                note=f"200ma now {ma200:.4f}  vs {k} bars ago {ma200_old:.4f}",
            )
        )
    else:
        out.append(GateResult("TT3_200ma_uptrend", False, ma200, 0, "not enough history"))

    # TT-4: 50-MA > 150-MA AND > 200-MA
    out.append(
        GateResult(
            "TT4_50ma_above_150_and_200",
            passed=(ma50 > ma150 and ma50 > ma200),
            value=ma50,
            threshold=max(ma150, ma200),
            note=f"ma50={ma50:.4f}",
        )
    )

    # TT-5: price > 50-MA
    out.append(
        GateResult(
            "TT5_price_above_50ma",
            passed=(px > ma50),
            value=px,
            threshold=ma50,
        )
    )

    # TT-6: price ≥ 30% above 200-bar low
    lo_200 = df["low"].iloc[-params["ma_200"] :].min()
    above_pct = (px / lo_200 - 1) * 100 if lo_200 > 0 else 0.0
    out.append(
        GateResult(
            "TT6_above_low_30pct",
            passed=(above_pct >= params["min_above_low_pct"]),
            value=above_pct,
            threshold=params["min_above_low_pct"],
            note=f"price {above_pct:+.1f}% above 200-bar low ({lo_200:.4f})",
        )
    )

    # TT-7: price within 25% of 200-bar high
    hi_200 = df["high"].iloc[-params["ma_200"] :].max()
    below_pct = (1 - px / hi_200) * 100 if hi_200 > 0 else 100.0
    out.append(
        GateResult(
            "TT7_within_25pct_of_high",
            passed=(below_pct <= params["max_below_high_pct"]),
            value=below_pct,
            threshold=params["max_below_high_pct"],
            note=f"price {below_pct:+.1f}% below 200-bar high ({hi_200:.4f})",
        )
    )

    # TT-8: relative-strength rank vs BTC over last `rs_lookback` bars
    if btc_df is not None and len(btc_df) >= params["rs_lookback"]:
        token_ret = (close[-1] / close[-params["rs_lookback"]]) - 1
        btc_close = btc_df["close"].astype(float).values
        if len(btc_close) >= params["rs_lookback"]:
            btc_ret = (btc_close[-1] / btc_close[-params["rs_lookback"]]) - 1
            # simple rank: token_ret > btc_ret => 100, else scaled
            rs_rank = 100.0 if token_ret > btc_ret else max(0.0, 50 + (token_ret - btc_ret) * 100)
            rs_rank = min(100.0, rs_rank)
            out.append(
                GateResult(
                    "TT8_relative_strength_vs_BTC",
                    passed=(rs_rank >= params["rs_rank_min"]),
                    value=rs_rank,
                    threshold=params["rs_rank_min"],
                    note=f"token_ret={token_ret * 100:+.1f}%  btc_ret={btc_ret * 100:+.1f}%  rs_rank≈{rs_rank:.0f}",
                )
            )
        else:
            out.append(
                GateResult(
                    "TT8_relative_strength_vs_BTC",
                    True,
                    50,
                    50,
                    "insufficient BTC history; gate skipped",
                )
            )
    else:
        out.append(
            GateResult(
                "TT8_relative_strength_vs_BTC",
                True,
                50,
                50,
                "BTC reference unavailable; gate skipped",
            )
        )

    return out


# ════════════════════════════════════════════════════════════════════════════
#   GATE 2 — BASE STRUCTURE: contractions, volume dry-up, tightness, pivot
# ════════════════════════════════════════════════════════════════════════════


def detect_contractions(df: pd.DataFrame, params: dict) -> list[Contraction]:
    """
    Identify successive pullbacks within the most recent base.
    Walk the swing-pivot sequence (high→low→high→low...) over the
    last `base_lookback` bars and emit each high→low leg as a Contraction.
    """
    n = len(df)
    if n < params["base_lookback"] + params["swing_strength"] * 2:
        return []

    sub = df.iloc[-params["base_lookback"] :].reset_index(drop=True)
    highs = sub["high"].values
    lows = sub["low"].values
    vols = sub["volume"].values
    ts = pd.to_datetime(sub["timestamp"]).astype(str).values

    k = params["swing_strength"]
    pivot_h_idx = _find_pivot_highs(highs, k)
    pivot_l_idx = _find_pivot_lows(lows, k)

    # Interleave pivots in chronological order, marking type
    pivots = sorted(
        [(i, "H") for i in pivot_h_idx] + [(i, "L") for i in pivot_l_idx],
        key=lambda x: x[0],
    )

    # Walk sequentially building H→L pairs (a contraction = high then next low)
    contractions: list[Contraction] = []
    i = 0
    while i < len(pivots) - 1:
        ph_i, ph_t = pivots[i]
        if ph_t != "H":
            i += 1
            continue
        # find next "L" pivot after this H
        for j in range(i + 1, len(pivots)):
            pl_i, pl_t = pivots[j]
            if pl_t == "L" and pl_i > ph_i:
                # form the contraction
                if highs[ph_i] > 0:
                    depth = (highs[ph_i] - lows[pl_i]) / highs[ph_i] * 100
                else:
                    depth = 0.0
                # skip noise: only meaningful contractions
                if depth >= 1.0:
                    avg_vol = float(np.mean(vols[ph_i : pl_i + 1])) if pl_i > ph_i else 0.0
                    contractions.append(
                        Contraction(
                            high_idx=ph_i,
                            high_ts=ts[ph_i],
                            high_px=float(highs[ph_i]),
                            low_idx=pl_i,
                            low_ts=ts[pl_i],
                            low_px=float(lows[pl_i]),
                            depth_pct=float(depth),
                            duration_bars=int(pl_i - ph_i),
                            avg_volume=avg_vol,
                        )
                    )
                i = j  # next iteration starts looking for H after this L
                break
        else:
            break

    return contractions


def evaluate_base_structure(
    df: pd.DataFrame, contractions: list[Contraction], params: dict
) -> tuple[list[GateResult], float, float]:
    """Returns (list of gates, pivot_price, distance_to_pivot_pct)."""
    out: list[GateResult] = []

    # ── B-1: minimum number of contractions ─────────────────────────────────
    out.append(
        GateResult(
            "B1_min_contractions",
            passed=(len(contractions) >= params["min_contractions"]),
            value=len(contractions),
            threshold=params["min_contractions"],
        )
    )

    # ── B-2: progressive decay (each ≤ decay_ratio_max × previous) ─────────
    if len(contractions) >= 2:
        ratios = []
        for i in range(1, len(contractions)):
            prev_d = contractions[i - 1].depth_pct
            curr_d = contractions[i].depth_pct
            if prev_d > 0:
                ratios.append(curr_d / prev_d)
        all_decay = all(r <= params["decay_ratio_max"] for r in ratios)
        out.append(
            GateResult(
                "B2_progressive_decay",
                passed=all_decay,
                value=float(max(ratios)) if ratios else 1.0,
                threshold=params["decay_ratio_max"],
                note=f"ratios = {[round(r, 2) for r in ratios]}",
            )
        )
        # ── B-3: total decay last/first ≤ min_total_decay ────────────────
        first_d = contractions[0].depth_pct
        last_d = contractions[-1].depth_pct
        total_decay = last_d / first_d if first_d > 0 else 1.0
        out.append(
            GateResult(
                "B3_total_decay",
                passed=(total_decay <= params["min_total_decay"]),
                value=total_decay,
                threshold=params["min_total_decay"],
                note=f"first={first_d:.2f}%  last={last_d:.2f}%  ratio={total_decay:.2f}",
            )
        )
    else:
        out.append(
            GateResult(
                "B2_progressive_decay",
                False,
                0,
                params["decay_ratio_max"],
                "fewer than 2 contractions",
            )
        )
        out.append(
            GateResult(
                "B3_total_decay", False, 0, params["min_total_decay"], "fewer than 2 contractions"
            )
        )

    # ── B-4: volume dry-up — last contraction's avg vol vs prior's ────────
    if len(contractions) >= 2:
        prev_v = contractions[-2].avg_volume
        last_v = contractions[-1].avg_volume
        ratio = last_v / prev_v if prev_v > 0 else 1.0
        out.append(
            GateResult(
                "B4_volume_dryup",
                passed=(ratio <= params["vol_dryup_ratio_max"]),
                value=ratio,
                threshold=params["vol_dryup_ratio_max"],
                note=f"prior_avg_vol={prev_v:.1f}  last_avg_vol={last_v:.1f}",
            )
        )
    else:
        out.append(GateResult("B4_volume_dryup", False, 1.0, params["vol_dryup_ratio_max"], "n/a"))

    # ── B-5: tight final base — ATR/price percentile rank ─────────────────
    n = len(df)
    if n >= params["tight_pct_rank_window"] + params["tight_atr_window"]:
        atr_series = _atr(df, params["tight_atr_window"])
        ratio_series = atr_series / df["close"].astype(float)
        recent = ratio_series.iloc[-params["tight_pct_rank_window"] :]
        current = float(ratio_series.iloc[-1])
        rank = _percentile_rank(recent, current)
        out.append(
            GateResult(
                "B5_tight_final_base",
                passed=(rank <= params["tight_pct_rank_max"]),
                value=rank,
                threshold=params["tight_pct_rank_max"],
                note=f"current ATR/px = {current:.5f}  rank={rank:.0f}th pct",
            )
        )
    else:
        out.append(GateResult("B5_tight_final_base", False, 100, 0, "insufficient history"))

    # ── B-6: pivot proximity — current price vs pivot ─────────────────────
    pivot_lb = params["pivot_lookback"]
    if n >= pivot_lb:
        pivot_px = float(df["high"].iloc[-pivot_lb:].max())
    else:
        pivot_px = float(df["high"].max())
    last_close = float(df["close"].iloc[-1])
    distance = (1 - last_close / pivot_px) * 100 if pivot_px > 0 else 100.0
    out.append(
        GateResult(
            "B6_pivot_proximity",
            passed=(0 <= distance <= params["pivot_proximity_pct"]),
            value=distance,
            threshold=params["pivot_proximity_pct"],
            note=f"pivot={pivot_px:.4f}  px={last_close:.4f}  {distance:+.2f}% away",
        )
    )

    return out, pivot_px, distance


# ════════════════════════════════════════════════════════════════════════════
#   COMPOSITE SCORING
# ════════════════════════════════════════════════════════════════════════════

# Each gate contributes a fixed weight; total = 100.
WEIGHTS = {
    # Trend Template (must-haves) — total 50 pts
    "TT1_price_above_150_and_200": 8,
    "TT2_150ma_above_200ma": 6,
    "TT3_200ma_uptrend": 8,
    "TT4_50ma_above_150_and_200": 6,
    "TT5_price_above_50ma": 4,
    "TT6_above_low_30pct": 4,
    "TT7_within_25pct_of_high": 6,
    "TT8_relative_strength_vs_BTC": 8,
    # Base structure (the VCP itself) — total 50 pts
    "B1_min_contractions": 8,
    "B2_progressive_decay": 10,
    "B3_total_decay": 8,
    "B4_volume_dryup": 8,
    "B5_tight_final_base": 8,
    "B6_pivot_proximity": 8,
}


def compute_score(all_gates: list[GateResult]) -> float:
    total = 0.0
    for g in all_gates:
        if g.passed:
            total += WEIGHTS.get(g.name, 0)
    return float(total)


def build_diagnostic(
    symbol: str,
    all_gates: list[GateResult],
    contractions: list[Contraction],
    score: float,
    pivot_px: float,
    distance_pct: float,
) -> str:
    failed = [g.name for g in all_gates if not g.passed]
    parts = [f"{symbol}  Score={score:.0f}/100"]
    if not failed:
        parts.append("ALL gates passed.")
    else:
        parts.append(f"Failed: {', '.join(failed)}")
    if contractions:
        depths = [f"T{i + 1}={c.depth_pct:.1f}%" for i, c in enumerate(contractions)]
        parts.append(f"Contractions: {' → '.join(depths)}")
    parts.append(f"Pivot={pivot_px:.4f} ({distance_pct:+.2f}% away)")
    return " | ".join(parts)


# ════════════════════════════════════════════════════════════════════════════
#   MAIN ENTRYPOINT — detect_vcp(df, ...) → VCPResult
# ════════════════════════════════════════════════════════════════════════════


def detect_vcp(
    df: pd.DataFrame,
    symbol: str = "?",
    params: Optional[dict] = None,
    btc_df: Optional[pd.DataFrame] = None,
) -> VCPResult:
    """
    Run the full VCP pipeline on a DataFrame of OHLCV bars.

    df must have columns: timestamp, open, high, low, close, volume.
    Returns a VCPResult with every gate's pass/fail and a composite score.
    """
    params = {**DEFAULT_PARAMS, **(params or {})}

    # Resample to scan_tf
    try:
        rdf = _resample(df, params["scan_tf"])
    except Exception as e:
        return VCPResult(
            symbol=symbol,
            scan_tf=params["scan_tf"],
            bar_count=0,
            last_close=0,
            last_ts="",
            error=f"resample failed: {e}",
        )

    n = len(rdf)
    if n < params["ma_200"] + 10:
        return VCPResult(
            symbol=symbol,
            scan_tf=params["scan_tf"],
            bar_count=n,
            last_close=float(rdf["close"].iloc[-1]) if n else 0,
            last_ts=str(rdf["timestamp"].iloc[-1]) if n else "",
            error=f"insufficient bars after resample to {params['scan_tf']} ({n} < {params['ma_200'] + 10})",
        )

    if btc_df is not None:
        try:
            btc_df = _resample(btc_df, params["scan_tf"])
        except Exception:
            btc_df = None

    # Trend Template
    tt_gates = evaluate_trend_template(rdf, params, btc_df)

    # Base structure
    contractions = detect_contractions(rdf, params)
    base_gates, pivot_px, distance = evaluate_base_structure(rdf, contractions, params)

    all_gates = tt_gates + base_gates
    score = compute_score(all_gates)

    tt_pass_first5 = all(bool(g.passed) for g in tt_gates[:5])
    res = VCPResult(
        symbol=symbol,
        scan_tf=params["scan_tf"],
        bar_count=int(n),
        last_close=float(rdf["close"].iloc[-1]),
        last_ts=str(rdf["timestamp"].iloc[-1]),
        trend_template=[g.to_dict() for g in tt_gates],
        base=[g.to_dict() for g in base_gates],
        contractions=[c.to_dict() for c in contractions],
        pivot_price=float(pivot_px),
        distance_to_pivot_pct=float(distance),
        vcp_score=float(score),
        passed_strict=bool(score >= params["strict_score_min"]),
        passed_relaxed=bool(
            score >= params["relaxed_score_min"]
            and len(contractions) >= params["min_contractions"]
            and tt_pass_first5
        ),
        diagnostic_text=build_diagnostic(
            symbol, all_gates, contractions, score, pivot_px, distance
        ),
    )
    return res


# ════════════════════════════════════════════════════════════════════════════
#   STANDALONE SCAN — full universe
# ════════════════════════════════════════════════════════════════════════════


def _load_token_csv(path: str, recent_bars_5m: int = 6000) -> Optional[pd.DataFrame]:
    """Load only the last N 5-minute rows; sufficient for resampling to 1h × 200 bars."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            lines = fh.readlines()
        if len(lines) < 2:
            return None
        header = lines[:1]
        body = lines[max(1, len(lines) - recent_bars_5m) :]
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

    # Load BTC reference once for relative strength
    btc_path = os.path.join(DATA_DIR, "BTCUSDT_Master_Tick_Data.csv")
    btc_df = _load_token_csv(btc_path) if os.path.exists(btc_path) else None

    files = sorted(glob.glob(os.path.join(DATA_DIR, "*_Master_Tick_Data.csv")))
    if verbose:
        print(f"[VCP] Scanning {len(files)} tokens at scan_tf={params['scan_tf']}...")

    results: list[VCPResult] = []
    for idx, fp in enumerate(files):
        symbol = os.path.basename(fp).replace("_Master_Tick_Data.csv", "")
        df = _load_token_csv(fp)
        if df is None or df.empty:
            continue
        res = detect_vcp(df, symbol=symbol, params=params, btc_df=btc_df)
        results.append(res)
        if verbose and (idx + 1) % 50 == 0:
            print(f"  ... scanned {idx + 1}/{len(files)}")

    # Sort by composite score, descending
    results.sort(key=lambda r: r.vcp_score, reverse=True)

    out = {
        "scan_time_utc8": (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(
            timespec="seconds"
        ),
        "config": params,
        "n_tokens_scanned": len(results),
        "n_passed_strict": sum(1 for r in results if r.passed_strict),
        "n_passed_relaxed": sum(1 for r in results if r.passed_relaxed),
        "tokens": [r.to_dict() for r in results],
    }

    out_path = os.path.join(OUTPUT_DIR, UNIVERSE_FN)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    if verbose:
        print(f"[VCP] Wrote {out_path}")
        print(
            f"[VCP] Strict-pass: {out['n_passed_strict']}  |  Relaxed-pass: {out['n_passed_relaxed']}"
        )
        if results:
            print("[VCP] Top 10:")
            for r in results[:10]:
                marker = "★" if r.passed_strict else ("·" if r.passed_relaxed else " ")
                print(
                    f"  {marker} {r.symbol:<14} score={r.vcp_score:5.0f}  "
                    f"px={r.last_close:<10.4f}  pivot={r.pivot_price:<10.4f}  "
                    f"dist={r.distance_to_pivot_pct:+5.2f}%"
                )
    return out


# ════════════════════════════════════════════════════════════════════════════
#   PUBLIC HELPERS — for downstream strategies (v88_vcp.py, v91_vcp.py)
# ════════════════════════════════════════════════════════════════════════════


def load_universe(strict_only: bool = False, max_age_minutes: int = 90) -> set[str]:
    """
    Read vcp_universe.json. Returns set of symbols passing the requested gate.
    If JSON is older than max_age_minutes, prints a warning but still returns.
    Returns empty set if file is missing.
    """
    path = os.path.join(OUTPUT_DIR, UNIVERSE_FN)
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        scan_time = pd.to_datetime(data["scan_time_utc8"])
        age_min = (pd.Timestamp.now() - scan_time).total_seconds() / 60
        if age_min > max_age_minutes:
            print(f"[VCP] WARNING: universe file is {age_min:.0f} min old (max {max_age_minutes})")
        out = set()
        for t in data.get("tokens", []):
            ok = t["passed_strict"] if strict_only else t["passed_relaxed"]
            if ok:
                out.add(t["symbol"])
        return out
    except Exception as e:
        print(f"[VCP] load_universe failed: {e}")
        return set()


# ════════════════════════════════════════════════════════════════════════════
#   CLI
# ════════════════════════════════════════════════════════════════════════════


def _cli():
    p = argparse.ArgumentParser(description="VCP scanner — Volatility Contraction Pattern detector")
    p.add_argument("--tf", default=None, help="scan timeframe: 5m | 15m | 1h | 4h (default 1h)")
    p.add_argument("--symbol", default=None, help="scan one symbol only and print its diagnostic")
    p.add_argument("--quiet", action="store_true", help="suppress progress output")
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
        btc_path = os.path.join(DATA_DIR, "BTCUSDT_Master_Tick_Data.csv")
        btc_df = _load_token_csv(btc_path) if os.path.exists(btc_path) else None
        res = detect_vcp(df, symbol=sym, params=params, btc_df=btc_df)
        print(json.dumps(res.to_dict(), indent=2, default=str))
        sys.exit(0)

    scan_universe(params=params, verbose=not args.quiet)


if __name__ == "__main__":
    _cli()
