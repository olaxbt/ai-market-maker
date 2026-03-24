"""HTTP + WebSocket server for live/replay FlowEvent streams."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from .payload_adapter import build_nexus_payload
from .schema_validation import validate_nexus_payload

RUNS_DIR = Path(".runs")
LATEST_RUN_FILE = RUNS_DIR / "latest_run.txt"

app = FastAPI(title="AI Market Maker Flow Stream", version="0.1.0")


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
def run_payload(run_id: str) -> JSONResponse:
    log_path = _resolve_run_log(run_id)
    payload, _ = build_nexus_payload(log_path)
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
