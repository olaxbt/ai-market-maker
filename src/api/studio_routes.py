"""Studio: hosted-friendly chat endpoint.

This endpoint is meant to guide users:
- how to clone/install/run locally
- how to publish results to leaderboard
- where to browse tools

It intentionally avoids "doing" heavy execution on behalf of a hosted site.
"""

from __future__ import annotations

import logging
import os
import re
import time
from collections import deque
from typing import Any, Literal, TypedDict

import anyio
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.backtest_routes import (
    DemoBacktestRequest,
    PresetBacktestRequest,
    QuickBacktestRequest,
    get_backtest_iterations,
    get_backtest_job,
    post_demo_backtest_async,
    post_preset_backtest,
    post_preset_backtest_async,
    post_quick_backtest,
    post_quick_backtest_async,
)
from config.app_settings import load_app_settings
from config.env_parse import env_bool
from config.llm_env import llm_key_available
from config.llm_mode import llm_mode_enabled
from llm.openai_client import run_tool_calling_chat
from llm.tool_registry import ToolSpec, nexus_tool_specs

router = APIRouter(tags=["studio"])
logger = logging.getLogger(__name__)

REPO_URL = "https://github.com/olaxbt/ai-market-maker"
HOSTED_MODE_ENV = "AIMM_HOSTED_STUDIO"  # explicit override for Docker / hosted


class ChatTurn(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    text: str = Field("", max_length=20_000)


class StudioChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=20_000)
    conversation: list[ChatTurn] | None = None


class StepToolCall(TypedDict):
    action: Literal["tool_call"]
    tool: str
    text: str


class StepToolResult(TypedDict):
    action: Literal["tool_result"]
    tool: str
    text: str


class StepMessage(TypedDict):
    action: Literal["message"]
    text: str


class StepNavigate(TypedDict):
    action: Literal["navigate"]
    path: str


Step = StepToolCall | StepToolResult | StepMessage | StepNavigate


# Very small in-memory rate limit per IP (best-effort).
_RL: dict[str, deque[float]] = {}
_RL_WINDOW_SEC = 30.0
_RL_MAX_REQ = 12  # 12 / 30s per IP

_TITLE_RL: dict[str, deque[float]] = {}
_TITLE_RL_WINDOW_SEC = 60.0
_TITLE_RL_MAX_REQ = 20  # cheap title calls / 60s per IP


def _client_id(request: Request) -> str:
    # Prefer X-Forwarded-For when behind a proxy.
    xff = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if xff:
        return xff
    host = getattr(getattr(request, "client", None), "host", None)
    return host or "unknown"


def _rate_limit_or_429(request: Request) -> None:
    cid = _client_id(request)
    now = time.time()
    q = _RL.get(cid)
    if q is None:
        q = deque()
        _RL[cid] = q
    # prune
    cutoff = now - _RL_WINDOW_SEC
    while q and q[0] < cutoff:
        q.popleft()
    if len(q) >= _RL_MAX_REQ:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limited",
                "hint": f"Too many messages. Limit is {_RL_MAX_REQ} per {_RL_WINDOW_SEC:.0f}s.",
            },
        )
    q.append(now)


def _rate_limit_title_or_429(request: Request) -> None:
    cid = _client_id(request)
    now = time.time()
    q = _TITLE_RL.get(cid)
    if q is None:
        q = deque()
        _TITLE_RL[cid] = q
    cutoff = now - _TITLE_RL_WINDOW_SEC
    while q and q[0] < cutoff:
        q.popleft()
    if len(q) >= _TITLE_RL_MAX_REQ:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limited",
                "hint": f"Too many title requests. Limit is {_TITLE_RL_MAX_REQ} per {_TITLE_RL_WINDOW_SEC:.0f}s.",
            },
        )
    q.append(now)


def _sanitize_studio_title_candidate(s: str) -> str | None:
    raw = "".join(ch for ch in (s or "").strip() if ch.isprintable())
    raw = raw.replace("\ufeff", "").strip()
    if not raw:
        return None
    first_line = raw.splitlines()[0].strip()
    t = re.sub(r"\s+", " ", first_line).strip()
    if len(t) >= 2 and ((t[0] == t[-1] == '"') or (t[0] == t[-1] == "'")):
        t = t[1:-1].strip()
    low = t.lower()
    if "http://" in low or "https://" in low:
        return None
    if len(t) < 2 or len(t) > 52:
        return None
    return t[:52]


class StudioSuggestTitleRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)


def _studio_title_system_prompt() -> str:
    return (
        "You name chat threads for a developer product (AI Market Maker / trading studio).\n"
        "Output rules:\n"
        "- Reply with a single short title only (maximum 44 characters).\n"
        "- No quotes, bullets, numbering, markdown, or preamble.\n"
        "- Encode the user's main goal or topic; omit filler words.\n"
    )


def _studio_title_llm(user_snippet: str) -> str:
    final_text, _tool_events = run_tool_calling_chat(
        system=_studio_title_system_prompt(),
        user=f"First user message:\n{user_snippet}",
        tool_specs=[],
        model=os.getenv("AIMM_STUDIO_TITLE_MODEL") or os.getenv("AIMM_LLM_MODEL") or None,
        temperature=0.2,
        max_tool_rounds=0,
        max_tokens=40,
        conversation_history=None,
    )
    return (final_text or "").strip()


def _studio_title_sync(message: str) -> str | None:
    cleaned = _safe_text(message).strip()
    if not cleaned:
        return None
    snippet = cleaned[:500]
    raw = _studio_title_llm(snippet)
    return _sanitize_studio_title_candidate(raw)


def _studio_openai_history(
    turns: list[ChatTurn] | None,
    *,
    latest_user: str,
    max_turns: int = 12,
) -> list[dict[str, str]]:
    """Map request conversation to OpenAI user/assistant history (excludes latest user line)."""
    rows: list[dict[str, str]] = []
    if not turns:
        return rows
    for t in turns:
        if t.role not in ("user", "assistant"):
            continue
        text = (t.text or "").strip()
        if not text:
            continue
        rows.append({"role": t.role, "content": text})
    lt = latest_user.strip()
    while rows and rows[-1]["role"] == "user" and rows[-1]["content"] == lt:
        rows.pop()
    if len(rows) > max_turns:
        rows = rows[-max_turns:]
    return rows


def _social_intent(msg: str) -> str | None:
    """Lightweight chitchat routing for the no-LLM fallback (and to avoid spammy 'try onboarding')."""
    s = (msg or "").strip()
    if not s or len(s) > 56:
        return None
    lower = s.lower().rstrip("!.?").strip()
    productish = (
        "backtest",
        "paper",
        "publish",
        "leaderboard",
        "aimm",
        "trade",
        "trading",
        "console",
        "nexus",
        "docker",
        "clone",
        "repo",
        "run_id",
        "run id",
        "tool",
        "signal",
    )
    if any(k in lower for k in productish):
        return None
    if any(c.isdigit() for c in s):
        return None
    toks = lower.split()
    if not toks:
        return None
    if lower.startswith(("thanks", "thank you", "thx", "appreciate")) or lower in ("ty", "thx"):
        return "thanks"
    if any(
        k in lower
        for k in (
            "how are you",
            "how r u",
            "how's it going",
            "how is it going",
            "you ok",
            "you okay",
        )
    ):
        return "how_are_you"
    if len(toks) <= 3 and toks[0] in ("hi", "hello", "hey", "yo", "sup", "hiya", "howdy"):
        return "greeting"
    if len(toks) <= 4 and (
        lower.startswith("good morning")
        or lower.startswith("good afternoon")
        or lower.startswith("good evening")
    ):
        return "greeting"
    return None


def _social_reply(kind: str) -> str:
    if kind == "how_are_you":
        return (
            "I’m doing well — thanks for asking.\n\n"
            "I’m the Studio guide for **AIMM** (AI Market Maker): setup, backtests, publishing to the leaderboard, "
            "and where to click in the app. What would you like to do next?"
        )
    if kind == "thanks":
        return "You’re welcome. If you want to dig into AIMM (runs, tools, or publishing), just say what you’re trying to achieve."
    return (
        "Hi — I’m here to help with **AIMM**.\n\n"
        "I can walk you through **getting started**, **backtests / paper** (local), **publishing** to the leaderboard, "
        "or point you to **Console / Guides**. What’s your goal today?"
    )


def _detect_intent(msg: str) -> str:
    s = (msg or "").strip()
    lower = s.lower()
    if not s:
        return "help"
    social = _social_intent(msg)
    if social:
        return f"social:{social}"
    if any(
        k in lower
        for k in ("what is this", "what is", "overview", "how it works", "architecture", "agentic")
    ):
        return "overview"
    if "openclaw" in lower or "claw" in lower:
        return "openclaw"
    if any(k in lower for k in ("onboarding", "get started", "clone", "install", "setup")):
        return "onboarding"
    if "publish" in lower or "provider key" in lower:
        return "publish"
    if "tools" in lower or "tool browser" in lower:
        return "tools"
    if any(
        k in lower
        for k in ("control center", "control", "ops", "selftest", "health", "capabilities")
    ):
        return "control"
    if any(k in lower for k in ("run", "backtest", "paper", "live", "execute", "trade", "start")):
        return "execution"
    return "help"


def _wants_navigation(msg: str) -> bool:
    lower = (msg or "").strip().lower()
    if not lower:
        return False
    return any(
        k in lower
        for k in (
            "open ",
            "go to",
            "goto",
            "take me to",
            "navigate",
            "show me",
            "bring me to",
            "redirect",
            "/leaderboard",
            "/console",
            "/control",
            "/tools",
            "/get-started",
        )
    )


def _overview_text() -> str:
    return (
        "**AIMM (AI Market Maker) — what it is**\n\n"
        "AIMM is an agentic trading / research OS with an auditable execution loop. The core idea is: every run produces "
        "**receipts** (what data was reviewed, what was decided, what tools were used) so results are reproducible and debuggable.\n\n"
        "**What you can do**\n"
        "- **Backtest / paper / (optionally) live** strategies locally using the Control Center\n"
        "- Inspect **run receipts** (iterations) to understand decisions bar-by-bar\n"
        "- Publish runs to the hosted **Leaderboard** so others can compare results\n"
        "- Browse the system's **Tools** (capabilities) used by agents\n\n"
        "**How the product is structured**\n"
        "- **Studio**: guided chat workspace (explain + point you to the right panels)\n"
        "- **Control**: run backtests, publish results, inspect receipts, self-test\n"
        "- **Leaderboard**: view published results + signals\n"
        "- **Nexus**: topology / agents / research / monitor (dev-oriented)\n\n"
        "Tell me what you’re trying to achieve (strategy, signals, or understanding receipts) and I’ll map the exact flow."
    )


def _steps_for(intent: str) -> list[Step]:
    if intent.startswith("social:"):
        kind = intent.split(":", 1)[1]
        return [{"action": "message", "text": _social_reply(kind)}]
    if intent == "overview":
        return [{"action": "message", "text": _overview_text()}]
    if intent == "openclaw":
        return [
            {
                "action": "message",
                "text": (
                    "**OpenClaw-style memory in AIMM**\n\n"
                    "AIMM emphasizes **auditable, bounded memory** via receipts: the agent’s reviewed data, decisions, and tool usage are recorded "
                    "so you can reproduce and debug runs without hidden state.\n\n"
                    "Where to look:\n"
                    f"- Repo: `{REPO_URL}`\n"
                    "- Run receipts: `iterations.jsonl` (linked from Control Center after a run)\n\n"
                    "If you mean chat-session memory vs trading-run memory, tell me which one and I’ll explain the exact artifacts."
                ),
            }
        ]
    if intent == "onboarding":
        return [
            {
                "action": "message",
                "text": f"Clone the repo and run locally:\n\nRepo: `{REPO_URL}`\n\nI opened **Get Started** with copy/paste commands.",
            },
        ]
    if intent == "tools":
        return [
            {
                "action": "message",
                "text": (
                    "**Tools (capabilities) — what they are**\n\n"
                    "Tools are the backend-owned actions the agent can call (data fetch, ops, publishing, diagnostics). "
                    "They’re exposed as a catalog so users can understand what the system can do.\n\n"
                    "Useful pages:\n"
                    "- Tool Browser: `/tools`\n"
                    "- Capabilities: `/capabilities`\n\n"
                    "Ask me what you want to do (e.g. “run a backtest” or “publish a result”) and I’ll list the exact tools involved."
                ),
            }
        ]
    if intent == "control":
        return [
            {
                "action": "message",
                "text": (
                    "In **Control Center** you can:\n"
                    "- Run a quick backtest (returns a `run_id`)\n"
                    "- Publish that backtest into the leaderboard DB as provider `local`\n"
                    "- Inspect **Run receipts** (iterations) to see what data was reviewed and why decisions happened\n"
                    "- Check `/ops/selftest` + `/capabilities` so the UI never lies"
                ),
            },
        ]
    if intent == "publish":
        return [
            {
                "action": "message",
                "text": (
                    "**Publishing flow**\n\n"
                    "1) Run locally (backtest/paper)\n"
                    "2) Submit result to the hosted leaderboard (`/leadpage/external_result`) using your provider key\n"
                    "3) Verify it appears on `/leaderboard`"
                ),
            },
        ]
    if intent == "execution":
        settings = load_app_settings()
        hosted = env_bool(os.environ, HOSTED_MODE_ENV, default=settings.control_plane.hosted_studio)
        if not hosted:
            return [
                {
                    "action": "message",
                    "text": (
                        "You’re running **locally**, so you can execute safely via the Control Center:\n\n"
                        "1) Run a backtest → capture `run_id`\n"
                        "2) Publish it (provider `local`) → verify on `/leaderboard`\n"
                        "3) Iterate in Studio with clear, repeatable loops"
                    ),
                },
            ]
        return [
            {
                "action": "message",
                "text": (
                    "**Hosted mode:** this site is for evaluation.\n\n"
                    "To run backtests/paper/live trading, clone the repo and run locally.\n"
                    f"Repo: `{REPO_URL}`"
                ),
            },
        ]
    return [
        {
            "action": "message",
            "text": "Try: `onboarding`, `publish to leaderboard`, or `tools`. If you want to run backtests/paper trading, you’ll do it locally after cloning the repo.",
        }
    ]


_SAFE_PATHS: dict[str, str] = {
    "leaderboard": "/leaderboard",
    "console": "/console",
    "backtests": "/backtests",
    "control": "/control",
    "tools": "/tools",
    "guides": "/guides?section=get-started",
    "workspace": "/workspace",
    "paper": "/console?view=monitor",
    "queue": "/console?view=monitor",
}


def _ui_navigate(path: str) -> dict[str, Any]:
    p = (path or "").strip()
    if not p:
        return {"status": "error", "error": "missing_path"}
    # Allow a known set of internal routes only.
    if p in _SAFE_PATHS.values():
        return {"status": "ok", "path": p}
    key = p.lower().strip().lstrip("/")
    if key in _SAFE_PATHS:
        return {"status": "ok", "path": _SAFE_PATHS[key]}
    return {
        "status": "error",
        "error": "unsafe_path",
        "hint": f"Allowed: {sorted(_SAFE_PATHS.values())}",
    }


def _tool_catalog() -> dict[str, Any]:
    # Mirror `GET /tools` output shape (subset) so Studio can browse capabilities without inventing them.
    return {
        "status": "ok",
        "tools": [
            {"id": "runs.payload", "path": "/runs/latest/payload", "method": "GET"},
            {"id": "backtest.quick", "path": "/backtests/quick", "method": "POST"},
            {
                "id": "backtest.iterations",
                "path": "/backtests/{run_id}/iterations",
                "method": "GET",
            },
            {"id": "leaderboard.rows", "path": "/leadpage/leaderboard", "method": "GET"},
            {"id": "leaderboard.submit", "path": "/leadpage/external_result", "method": "POST"},
        ],
    }


def _llm_system_prompt(*, hosted: bool) -> str:
    hosted_note = (
        "You are running in HOSTED mode: do not claim you can run backtests/paper/live trading here. "
        "Instead, guide the user to clone the repo and run locally."
        if hosted
        else "You are running in LOCAL mode: you may guide the user through running backtests/paper locally."
    )
    return (
        "You are the Studio assistant for AI Market Maker (AIMM).\n"
        "You are a capable guide: infer intent from the whole conversation (not isolated keywords).\n\n"
        "Behavior:\n"
        "- Reply naturally to greetings and small talk, then steer toward how you can help with AIMM.\n"
        "- For product questions: be specific, structured (short headings/bullets), and accurate.\n"
        "- When the user names an action (“open leaderboard”, “show tools”), call ui.navigate *before* or *while* "
        "answering — do not invent routes.\n"
        "- Prefer calling platform.tool_catalog when the user asks what the system/API can do, then summarize.\n"
        "- Prefer tools over guessing when listing endpoints or capabilities.\n\n"
        "Tools:\n"
        "- ui.navigate(path): allowed internal routes only (see tool schema hints).\n"
        "- platform.tool_catalog(): small stable catalog of Flow endpoints.\n"
        "- backtests.quick(...): run a quick backtest (local).\n"
        "- backtests.preset(...): run a preset backtest (local).\n"
        "- backtests.iterations(run_id,...): fetch iteration receipts for a run.\n"
        "- If the user asks to run *a* backtest once, call **at most one** of backtests.quick_async, "
        "backtests.preset_async, or backtests.demo_async in that turn (never start several runs in parallel).\n"
        "- nexus.fetch_market_depth(symbol, limit): read-only example.\n\n"
        f"- {hosted_note}\n"
        "Repo for local runs: https://github.com/olaxbt/ai-market-maker\n"
        "Never say you 'cannot execute' if a tool exists to do it; instead call the tool.\n"
    )


def _tool_http_error(exc: HTTPException) -> dict[str, Any]:
    detail = exc.detail
    if isinstance(detail, dict):
        return {"status": "error", **detail, "http_status": exc.status_code}
    return {"status": "error", "error": str(detail), "http_status": exc.status_code}


def _safe_text(s: str) -> str:
    """Clean up common formatting glitches from LLM output."""
    t = (s or "").strip()
    # Sometimes the model starts a fence but never closes it.
    if t.endswith("```json") or t.endswith("```"):
        t = t.rsplit("```", 1)[0].rstrip()
    return t


def _tool_result_text(result: Any) -> str:
    """Prefer JSON for tool results so the UI can render safely."""
    try:
        if isinstance(result, (dict, list)):
            import json

            return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return str(result or "")


def _fallback_message_from_tool_events(tool_events: list[dict[str, Any]]) -> str | None:
    """If the model returns no final text, produce a helpful operator message."""
    for ev in reversed(tool_events or []):
        name = str(ev.get("name") or ev.get("wire_name") or "")
        if name in {
            "backtests.quick_async",
            "backtests_quick_async",
            "backtests.preset_async",
            "backtests_preset_async",
            "backtests.demo_async",
            "backtests_demo_async",
        }:
            res = ev.get("result")
            if isinstance(res, dict):
                rid = str(res.get("run_id") or "").strip()
                poll = str(res.get("poll") or "").strip()
                if rid:
                    return (
                        "Backtest started.\n\n"
                        f"- run_id: `{rid}`\n"
                        + (f"- poll: `{poll}`\n" if poll else "")
                        + "\nOpen `/backtests` for progress and results."
                    )
    return None


def _tool_backtests_quick(**kw: Any) -> dict[str, Any]:
    try:
        req = QuickBacktestRequest(**kw)
        return {"status": "ok", **post_quick_backtest(req)}
    except HTTPException as exc:
        return _tool_http_error(exc)


def _tool_backtests_quick_async(**kw: Any) -> dict[str, Any]:
    """Async quick backtest: returns run_id + poll path immediately."""
    try:
        req = QuickBacktestRequest(**kw)
        return {"status": "ok", **post_quick_backtest_async(req)}
    except HTTPException as exc:
        return _tool_http_error(exc)


def _tool_backtests_job(*, run_id: str) -> dict[str, Any]:
    """Poll a backtest job for progress or final result."""
    try:
        out = get_backtest_job(run_id=run_id)
        return {"status": "ok", **out}
    except HTTPException as exc:
        return _tool_http_error(exc)


def _tool_backtests_preset(**kw: Any) -> dict[str, Any]:
    try:
        req = PresetBacktestRequest(**kw)
        return {"status": "ok", **post_preset_backtest(req)}
    except HTTPException as exc:
        return _tool_http_error(exc)


def _tool_backtests_preset_async(**kw: Any) -> dict[str, Any]:
    """Async preset backtest: returns run_id + poll path immediately."""
    try:
        req = PresetBacktestRequest(**kw)
        return {"status": "ok", **post_preset_backtest_async(req)}
    except HTTPException as exc:
        return _tool_http_error(exc)


def _tool_backtests_demo_async(**kw: Any) -> dict[str, Any]:
    """Async README-style multi-symbol demo backtest (aligned OHLCV, one portfolio)."""
    try:
        req = DemoBacktestRequest(**kw)
        return {"status": "ok", **post_demo_backtest_async(req)}
    except HTTPException as exc:
        return _tool_http_error(exc)


def _tool_backtests_iterations(*, run_id: str, limit: int = 300) -> dict[str, Any]:
    try:
        out = get_backtest_iterations(run_id=run_id, limit=limit)
        return {"status": "ok", **out}
    except HTTPException as exc:
        return _tool_http_error(exc)


@router.post("/studio/suggest_title")
async def post_studio_suggest_title(
    request: Request, req: StudioSuggestTitleRequest
) -> dict[str, Any]:
    """Cheap LLM-backed title from the user's first message (short completion, sanitized)."""
    _rate_limit_title_or_429(request)
    msg = (req.message or "").strip()
    if not msg:
        raise HTTPException(
            status_code=400,
            detail={"error": "empty", "hint": "message is required"},
        )
    if not llm_mode_enabled(os.environ) or not llm_key_available(os.environ):
        raise HTTPException(
            status_code=503,
            detail={
                "error": "llm_required",
                "hint": "Set OPENAI_API_KEY to enable title suggestions.",
            },
        )
    try:
        title = await anyio.to_thread.run_sync(lambda: _studio_title_sync(msg))
    except Exception as exc:
        logger.warning("Studio title LLM failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "llm_unavailable",
                "hint": "Title suggestion failed. Try again later.",
            },
        ) from exc
    if not title:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "bad_title",
                "hint": "Could not produce a safe title from model output.",
            },
        )
    return {"title": title}


@router.post("/studio/chat")
async def post_studio_chat(request: Request, req: StudioChatRequest) -> dict[str, Any]:
    _rate_limit_or_429(request)
    msg = (req.message or "").strip()
    if not msg:
        return {
            "steps": [
                {
                    "action": "message",
                    "text": "Ask a question or describe what you’re trying to do.",
                }
            ]
        }

    settings = load_app_settings()
    hosted = env_bool(os.environ, HOSTED_MODE_ENV, default=settings.control_plane.hosted_studio)

    hist = _studio_openai_history(req.conversation, latest_user=msg)

    # Fast-path: running a backtest should never leave the UI "thinking" for minutes.
    # Start an async backtest immediately and return run_id + poll handle.
    low = msg.lower()
    if ("backtest" in low) and any(k in low for k in ("run", "start", "launch", "execute")):
        # README-style default: multi-symbol, 1d candles, 100 steps, Binance public OHLCV.
        out = _tool_backtests_demo_async(
            symbols="BTC/USDT,ETH/USDT,SOL/USDT",
            steps=100,
            interval_sec=86_400,
            exchange_id="binance",
        )
        rid = str(out.get("run_id") or "")
        poll = str(out.get("poll") or "")
        steps: list[Step] = [
            {
                "action": "tool_call",
                "tool": "backtests.demo_async",
                "text": "Calling backtests.demo_async…",
            },
            {
                "action": "tool_result",
                "tool": "backtests.demo_async",
                "text": _tool_result_text(out),
            },
            {
                "action": "message",
                "text": _safe_text(
                    "Backtest started.\n\n"
                    "- **Symbols**: `BTC/USDT, ETH/USDT, SOL/USDT`\n"
                    "- **Steps**: `100`\n"
                    "- **Timeframe**: `1d` (daily)\n"
                    "- **Exchange**: `binance`\n"
                    "- **Window**: Last `100` daily candles\n\n"
                    + (f"- **Run ID**: `{rid}`\n" if rid else "")
                    + (f"- **Poll interval**: `{poll}`\n" if poll else "")
                    + "\nCheck progress and results with `/backtests`.\n\n"
                    "To start a different backtest, just tell me the symbols, timeframe, and steps.\n"
                    "Example: `BTC/USDT,ETH/USDT` + `1h` + `200`"
                ),
            },
        ]
        return {"steps": steps}

    # Studio chat is LLM-first: if the LLM isn't configured/reachable, fail loudly rather than
    # returning canned keyword responses (which feel "dumb").
    if not llm_mode_enabled(os.environ) or not llm_key_available(os.environ):
        raise HTTPException(
            status_code=503,
            detail={
                "error": "llm_required",
                "hint": "Set OPENAI_API_KEY and ensure AIMM_LLM_MODE is not forcing LLM off.",
            },
        )

    tool_specs: list[ToolSpec] = []
    tool_specs.append(
        ToolSpec(
            name="ui.navigate",
            wire_name="ui_navigate",
            description="Navigate the UI to a safe internal route.",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
            handler=lambda **kw: _ui_navigate(str(kw.get("path") or "")),
        )
    )
    tool_specs.append(
        ToolSpec(
            name="platform.tool_catalog",
            wire_name="platform_tool_catalog",
            description="List a small stable tool catalog for AIMM.",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            handler=lambda **_kw: _tool_catalog(),
        )
    )
    tool_specs.append(
        ToolSpec(
            name="backtests.quick_async",
            wire_name="backtests_quick_async",
            description="Run a quick backtest locally (async) and return run_id + poll handle immediately.",
            parameters={
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "default": "BTC/USDT"},
                    "n_bars": {"type": "integer", "minimum": 20, "maximum": 100000, "default": 60},
                    "interval_sec": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 86400,
                        "default": 300,
                    },
                    "initial_cash": {"type": "number", "exclusiveMinimum": 0, "default": 10000},
                    "fee_bps": {"type": "number", "minimum": 0, "maximum": 500, "default": 10},
                    "max_steps": {"type": ["integer", "null"], "minimum": 1, "default": 60},
                    "exchange_id": {"type": "string", "default": "binance"},
                    "since_iso": {"type": ["string", "null"]},
                    "until_iso": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
            handler=_tool_backtests_quick_async,
        )
    )
    tool_specs.append(
        ToolSpec(
            name="backtests.job",
            wire_name="backtests_job",
            description="Poll an async backtest job by run_id for progress or completion result.",
            parameters={
                "type": "object",
                "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"],
                "additionalProperties": False,
            },
            handler=lambda **kw: _tool_backtests_job(run_id=str(kw.get("run_id") or "").strip()),
        )
    )
    tool_specs.append(
        ToolSpec(
            name="backtests.preset",
            wire_name="backtests_preset",
            description="Run a preset backtest locally (preset_id + defaults).",
            parameters={
                "type": "object",
                "properties": {
                    "preset_id": {"type": "string", "default": "macd_risk_v1"},
                    "ticker": {"type": "string", "default": "BTC/USDT"},
                    "n_bars": {"type": ["integer", "null"], "minimum": 20, "maximum": 100000},
                    "interval_sec": {"type": ["integer", "null"], "minimum": 60, "maximum": 86400},
                    "max_steps": {"type": ["integer", "null"], "minimum": 1},
                    "seed": {"type": ["integer", "null"], "minimum": 0},
                    "fee_bps": {"type": ["number", "null"], "minimum": 0, "maximum": 500},
                    "initial_cash": {"type": ["number", "null"], "exclusiveMinimum": 0},
                },
                "required": ["preset_id"],
                "additionalProperties": False,
            },
            handler=_tool_backtests_preset,
        )
    )
    tool_specs.append(
        ToolSpec(
            name="backtests.preset_async",
            wire_name="backtests_preset_async",
            description="Run a preset backtest locally (async) and return run_id + poll handle immediately.",
            parameters={
                "type": "object",
                "properties": {
                    "preset_id": {"type": "string", "default": "macd_risk_v1"},
                    "ticker": {"type": "string", "default": "BTC/USDT"},
                    "n_bars": {"type": ["integer", "null"], "minimum": 20, "maximum": 100000},
                    "interval_sec": {"type": ["integer", "null"], "minimum": 60, "maximum": 86400},
                    "max_steps": {"type": ["integer", "null"], "minimum": 1, "default": 120},
                    "seed": {"type": ["integer", "null"], "minimum": 0},
                    "fee_bps": {"type": ["number", "null"], "minimum": 0, "maximum": 500},
                    "initial_cash": {"type": ["number", "null"], "exclusiveMinimum": 0},
                },
                "required": ["preset_id"],
                "additionalProperties": False,
            },
            handler=_tool_backtests_preset_async,
        )
    )
    tool_specs.append(
        ToolSpec(
            name="backtests.demo_async",
            wire_name="backtests_demo_async",
            description="Run the README-style multi-symbol demo backtest (async) and return run_id + poll handle.",
            parameters={
                "type": "object",
                "properties": {
                    "symbols": {"type": "string", "default": "BTC/USDT,ETH/USDT,SOL/USDT"},
                    "steps": {"type": "integer", "minimum": 20, "maximum": 20000, "default": 100},
                    "interval_sec": {
                        "type": "integer",
                        "minimum": 60,
                        "maximum": 86400,
                        "default": 86400,
                    },
                    "exchange_id": {"type": "string", "default": "binance"},
                    "initial_cash": {"type": "number", "exclusiveMinimum": 0, "default": 10000},
                    "fee_bps": {"type": "number", "minimum": 0, "maximum": 500, "default": 10},
                },
                "additionalProperties": False,
            },
            handler=_tool_backtests_demo_async,
        )
    )
    tool_specs.append(
        ToolSpec(
            name="backtests.iterations",
            wire_name="backtests_iterations",
            description="Fetch iterations.jsonl receipts for a backtest run_id.",
            parameters={
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 5000, "default": 300},
                },
                "required": ["run_id"],
                "additionalProperties": False,
            },
            handler=lambda **kw: _tool_backtests_iterations(
                run_id=str(kw.get("run_id") or "").strip(),
                limit=int(kw.get("limit") or 300),
            ),
        )
    )
    # Add a small subset of Nexus tools (read-only by default).
    tool_specs.extend(nexus_tool_specs(include_write_tools=False))

    try:
        # Run tool-calling + any heavy tool handlers off the event loop thread.
        # NOTE: `anyio.to_thread.run_sync` does not accept kwargs for the *target* function;
        # wrap in a lambda/closure instead.
        final_text, tool_events = await anyio.to_thread.run_sync(
            lambda: run_tool_calling_chat(
                system=_llm_system_prompt(hosted=hosted),
                user=msg,
                tool_specs=tool_specs,
                model=os.getenv("AIMM_LLM_MODEL") or None,
                temperature=0.35,
                max_tool_rounds=4,
                max_tokens=1100,
                conversation_history=hist,
            )
        )
    except Exception as exc:
        logger.warning("Studio LLM unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "llm_unavailable",
                "hint": "LLM request failed. Verify provider/base_url/model and try again.",
            },
        ) from None

    steps: list[Step] = []
    for ev in tool_events:
        name = str(ev.get("name") or ev.get("wire_name") or "")
        steps.append({"action": "tool_call", "tool": name, "text": f"Calling {name}…"})
        steps.append(
            {
                "action": "tool_result",
                "tool": name,
                "text": _tool_result_text(ev.get("result")),
            }
        )
        if name == "ui.navigate":
            res = ev.get("result") or {}
            if isinstance(res, dict) and res.get("status") == "ok" and res.get("path"):
                steps.append({"action": "navigate", "path": str(res["path"])})

    final_clean = _safe_text(final_text)
    if final_clean.strip():
        steps.append({"action": "message", "text": final_clean})
    else:
        fb = _fallback_message_from_tool_events(tool_events)
        steps.append(
            {
                "action": "message",
                "text": fb or "I couldn’t produce a response. Try rephrasing your request.",
            }
        )
    return {"steps": steps}
