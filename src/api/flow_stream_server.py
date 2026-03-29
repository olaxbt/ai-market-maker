"""HTTP + WebSocket server for live/replay FlowEvent streams."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .backtest_routes import router as backtest_router
from .payload_adapter import build_nexus_payload
from .schema_validation import validate_nexus_payload

RUNS_DIR = Path(".runs")
LATEST_RUN_FILE = RUNS_DIR / "latest_run.txt"

app = FastAPI(title="AI Market Maker Flow Stream", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(backtest_router)


def _resolve_run_log(run_id: str) -> Path:
    if run_id == "latest" and LATEST_RUN_FILE.exists():
        latest = LATEST_RUN_FILE.read_text().strip()
        if latest:
            return RUNS_DIR / f"{latest}.events.jsonl"
    return RUNS_DIR / f"{run_id}.events.jsonl"


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True}


@app.get("/runs/latest")
def latest_run() -> dict[str, Any]:
    if not LATEST_RUN_FILE.exists():
        return {"run_id": None}
    return {"run_id": LATEST_RUN_FILE.read_text().strip() or None}


@app.get("/runs/{run_id}/events")
def run_events(run_id: str) -> JSONResponse:
    log_path = _resolve_run_log(run_id)
    _, events = build_nexus_payload(log_path)
    return JSONResponse({"run_id": log_path.stem.replace(".events", ""), "events": events})


@app.get("/runs/{run_id}/payload")
def run_payload(run_id: str, soft: bool = Query(False)) -> JSONResponse:
    """Nexus UI payload from flow events.

    Use ``soft=1`` while a run is in progress (schema may be loose).
    """
    log_path = _resolve_run_log(run_id)
    payload, _ = build_nexus_payload(log_path)
    if not soft:
        validate_nexus_payload(payload)
    return JSONResponse(payload)


@app.websocket("/ws/runs/{run_id}")
async def ws_run_payload(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    try:
        while True:
            log_path = _resolve_run_log(run_id)
            payload, _ = build_nexus_payload(log_path)
            validate_nexus_payload(payload)
            await websocket.send_json({"type": "payload", "payload": payload})
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return
