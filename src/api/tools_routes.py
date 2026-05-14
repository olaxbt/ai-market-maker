"""General tool registry for the platform.

This is a small, stable catalog of callable endpoints ("tools") that UIs and
agents can browse and invoke. It keeps the product understandable: users can
see what the system can do, and developers can quickly test each capability.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from fastapi import APIRouter

router = APIRouter(tags=["tools"])


class ToolHttp(TypedDict):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str


class ToolDef(TypedDict, total=False):
    id: str
    title: str
    category: str
    description: str
    http: ToolHttp
    input_example: dict[str, Any]
    output_example: dict[str, Any]


def _tool_registry() -> list[ToolDef]:
    # Keep ids global and short.
    return [
        {
            "id": "backtest.quick",
            "title": "Backtest: quick run",
            "category": "backtest",
            "description": "Run a multi-step bar replay backtest and write ledgers under .runs/backtests/<run_id>/.",
            "http": {"method": "POST", "path": "/backtests/quick"},
            "input_example": {
                "ticker": "BTC/USDT",
                "interval_sec": 3600,
                "n_bars": 200,
                "fee_bps": 5,
                "initial_cash": 10000,
                "agent_ids": ["n4", "n9", "n12"],
                "max_steps": 200,
            },
            "output_example": {"run_id": "bt_...", "metrics": {}, "evaluation": {}, "paths": {}},
        },
        {
            "id": "runs.payload",
            "title": "Runs: payload (UI replay)",
            "category": "runs",
            "description": "Fetch the Nexus UI payload assembled from flow events for a run id.",
            "http": {"method": "GET", "path": "/runs/{run_id}/payload"},
            "input_example": {"run_id": "latest", "soft": True},
            "output_example": {"metadata": {}, "topology": {}, "traces": [], "message_log": []},
        },
        {
            "id": "backtest.iterations",
            "title": "Backtest: iteration receipts",
            "category": "backtest",
            "description": "Fetch per-bar receipts (what the system saw/decided/errors) from .runs/backtests/<run_id>/iterations.jsonl.",
            "http": {"method": "GET", "path": "/backtests/{run_id}/iterations"},
            "input_example": {"run_id": "bt_...", "limit": 300},
            "output_example": {"run_id": "bt_...", "iterations": [{"ts": 0, "symbol": "BTC/USDT"}]},
        },
        {
            "id": "leaderboard.rows",
            "title": "Leaderboard rows",
            "category": "leaderboard",
            "description": "Fetch leaderboard result rows (local + external submissions).",
            "http": {"method": "GET", "path": "/leadpage/leaderboard"},
            "input_example": {},
            "output_example": {"rows": []},
        },
        {
            "id": "leaderboard.submit",
            "title": "Submit leaderboard result",
            "category": "leaderboard",
            "description": "Submit an external result summary (requires provider key if enabled).",
            "http": {"method": "POST", "path": "/leadpage/external_result"},
            "input_example": {
                "provider": "demo",
                "ticker": "BTC/USDT",
                "result_type": "backtest",
                "summary": {"total_return_pct": 1.0},
            },
            "output_example": {"ok": True},
        },
    ]


@router.get("/tools")
def get_tools() -> dict[str, Any]:
    return {"tools": _tool_registry()}


@router.get("/tools/{tool_id}")
def get_tool(tool_id: str) -> dict[str, Any]:
    tool_id = (tool_id or "").strip()
    for t in _tool_registry():
        if t.get("id") == tool_id:
            return {"tool": t}
    return {"tool": None, "error": "not_found", "tool_id": tool_id}
