"""Extract fields from Nexus JSON using OpenAPI-documented names first, then fallbacks.

Nexus standard error shape (when present): ``{"code", "message", "details"}`` under HTTP errors —
see ``parse_nexus_error_body``. Response bodies often use ``success`` + ``data`` nesting.
"""

from __future__ import annotations

from typing import Any


def unwrap_data(payload: Any) -> Any:
    """If ``payload`` is ``{success, data}``, return ``data``; else return ``payload``."""
    if not isinstance(payload, dict):
        return payload
    if "data" in payload and payload.get("success") is not False:
        return payload.get("data")
    return payload


def first_float(obj: Any, *keys: str, default: float = 0.0) -> float:
    if not isinstance(obj, dict):
        return default
    for k in keys:
        v = obj.get(k)
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                continue
    return default


def first_str(obj: Any, *keys: str, default: str | None = None) -> str | None:
    if not isinstance(obj, dict):
        return default
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return default


def as_dict(obj: Any) -> dict[str, Any]:
    return obj if isinstance(obj, dict) else {}


def parse_nexus_error_body(body: Any) -> dict[str, Any] | None:
    """Return ``{code, message, details}`` if body matches Nexus error model."""
    d = as_dict(body)
    if "message" in d and ("code" in d or "error" in d):
        return {
            "code": d.get("code") or d.get("error"),
            "message": str(d.get("message") or ""),
            "details": d.get("details"),
        }
    return None


def heatmap_row_for_ticker(
    raw: dict[str, Any], ticker: str, base: str, nexus_id: str
) -> dict[str, Any] | None:
    """Pick heatmap row for symbol; supports documented fields ``mention_count``, ``bullish_ratio``, ``price_momentum``."""
    cells = raw.get("data") or raw.get("heatmap") or raw.get("symbols") or raw.get("rows")
    if not isinstance(cells, list):
        return None
    want = {base.upper(), nexus_id.upper(), ticker.replace("/", "").upper()}
    for row in cells:
        if not isinstance(row, dict):
            continue
        sym = str(
            row.get("symbol") or row.get("ticker") or row.get("pair") or row.get("name") or ""
        ).upper()
        if sym in want or any(sym.endswith(s) for s in want if len(s) <= 6):
            return row
        if base.upper() in sym or nexus_id.upper() in sym:
            return row
    return None


def technical_analysis_core(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize technical cache to a single dict (pattern, mood, S/R)."""
    data = unwrap_data(raw)
    if not isinstance(data, dict):
        return {}
    analysis = data.get("analysis") or data.get("data")
    if isinstance(analysis, dict):
        return analysis
    return data


def coin_inner_payload(raw_coin_response: dict[str, Any]) -> dict[str, Any]:
    """Inner coin object from ``GET /coin/{id}``."""
    d = unwrap_data(raw_coin_response)
    return as_dict(d)


def quant_summary_core(raw: dict[str, Any]) -> dict[str, Any]:
    d = unwrap_data(raw)
    return as_dict(d)
