"""HTTP + WebSocket server for live/replay FlowEvent streams."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.status import HTTP_401_UNAUTHORIZED

from .agent_prompt_routes import router as agent_prompt_router
from .backtest_routes import router as backtest_router
from .payload_adapter import build_nexus_payload
from .pm_routes import router as pm_router
from .runtime_settings_routes import router as runtime_settings_router
from .schema_validation import validate_nexus_payload

# Same as `src/main.py`: repo-root `.env` applies to the Flow API when started via uvicorn.
load_dotenv(override=True)

RUNS_DIR = Path(".runs")
LATEST_RUN_FILE = RUNS_DIR / "latest_run.txt"

DEFAULT_TAIL_EVENTS = int((os.getenv("AIMM_UI_TAIL_EVENTS") or "1200").strip() or "1200")
DEFAULT_TAIL_TRACES = int((os.getenv("AIMM_UI_TAIL_TRACES") or "350").strip() or "350")
DEFAULT_TAIL_MESSAGE_LOG = int((os.getenv("AIMM_UI_TAIL_MESSAGES") or "600").strip() or "600")

app = FastAPI(title="AI Market Maker Flow Stream", version="0.1.0")


def _expected_api_key() -> str | None:
    v = (os.getenv("AIMM_API_KEY") or "").strip()
    return v or None


def _extract_presented_key(request: Request) -> str | None:
    # Prefer explicit X-API-Key; allow Authorization: Bearer for common gateways.
    x = (request.headers.get("x-api-key") or "").strip()
    if x:
        return x
    auth = (request.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        return token or None
    return None


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    expected = _expected_api_key()
    if expected is None:
        return await call_next(request)

    # Always allow unauthenticated health checks.
    if request.url.path == "/health":
        return await call_next(request)

    # Allow same-host calls (e.g. Next.js proxy running on the same machine/container).
    # This keeps the web UI functional without leaking the key to browsers.
    client_host = getattr(getattr(request, "client", None), "host", None)
    if client_host in {"127.0.0.1", "::1"}:
        return await call_next(request)

    presented = _extract_presented_key(request)
    if presented != expected:
        return JSONResponse(
            {"error": "unauthorized", "hint": "Set x-api-key (or Authorization: Bearer)"},
            status_code=HTTP_401_UNAUTHORIZED,
        )

    return await call_next(request)


_cors_origins_raw = (os.getenv("AIMM_CORS_ORIGINS") or "*").strip()
_cors_allow_origins = (
    ["*"]
    if _cors_origins_raw == "*"
    else [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(backtest_router)
app.include_router(agent_prompt_router)
app.include_router(runtime_settings_router)
app.include_router(pm_router)


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
def run_events(
    run_id: str, tail: int = Query(DEFAULT_TAIL_EVENTS, ge=50, le=200_000)
) -> JSONResponse:
    log_path = _resolve_run_log(run_id)
    _, events = build_nexus_payload(log_path, tail_events=int(tail))
    return JSONResponse({"run_id": log_path.stem.replace(".events", ""), "events": events})


@app.get("/runs/{run_id}/payload")
def run_payload(
    run_id: str,
    soft: bool = Query(False),
    tail_events: int = Query(DEFAULT_TAIL_EVENTS, ge=50, le=200_000),
    tail_traces: int = Query(DEFAULT_TAIL_TRACES, ge=50, le=50_000),
    tail_messages: int = Query(DEFAULT_TAIL_MESSAGE_LOG, ge=50, le=100_000),
) -> JSONResponse:
    """Nexus UI payload from flow events.

    Use ``soft=1`` while a run is in progress (schema may be loose).
    """
    log_path = _resolve_run_log(run_id)
    payload, _ = build_nexus_payload(
        log_path,
        tail_events=int(tail_events),
        tail_traces=int(tail_traces),
        tail_message_log=int(tail_messages),
    )
    if not soft:
        validate_nexus_payload(payload)
    return JSONResponse(payload)


@app.websocket("/ws/runs/{run_id}")
async def ws_run_payload(websocket: WebSocket, run_id: str) -> None:
    expected = _expected_api_key()
    if expected is not None:
        client_host = getattr(getattr(websocket, "client", None), "host", None)
        if client_host in {"127.0.0.1", "::1"}:
            await websocket.accept()
        else:
            presented = (websocket.headers.get("x-api-key") or "").strip()
            if not presented:
                auth = (websocket.headers.get("authorization") or "").strip()
                if auth.lower().startswith("bearer "):
                    presented = auth.split(" ", 1)[1].strip()
            if not presented:
                presented = (websocket.query_params.get("api_key") or "").strip()
            if presented != expected:
                await websocket.close(code=1008)
                return
            await websocket.accept()
    else:
        await websocket.accept()
    try:
        while True:
            log_path = _resolve_run_log(run_id)
            payload, _ = build_nexus_payload(
                log_path,
                tail_events=DEFAULT_TAIL_EVENTS,
                tail_traces=DEFAULT_TAIL_TRACES,
                tail_message_log=DEFAULT_TAIL_MESSAGE_LOG,
            )
            # Validate payload shape but keep it cheap by validating only the trimmed payload.
            validate_nexus_payload(payload)
            await websocket.send_json({"type": "payload", "payload": payload})
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return
