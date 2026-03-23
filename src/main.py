import argparse
import asyncio
import logging
import os
import time
from pprint import pformat
from typing import Any, Callable

import ccxt
from dotenv import load_dotenv
from langgraph.graph import END, StateGraph

from agents.governance.risk_guard import RiskGuardAgent
from agents.liquidity_management import LiquidityManagementAgent
from agents.market_scan import MarketScanAgent
from agents.portfolio_management import PortfolioManagementAgent
from agents.price_pattern import PricePatternAgent
from agents.quant import QuantAgent
from agents.risk_management import RiskManagementAgent
from agents.sentiment import SentimentAgent
from agents.stat_arb import StatArbAgent
from agents.valuation import ValuationAgent
from config.run_mode import RunMode, load_run_mode
from flow_log import FlowEventRepo, get_flow_repo, set_flow_repo
from schemas.flow_events import FlowEvent
from schemas.state import HedgeFundState, initial_hedge_fund_state
from telemetry.logger import LogPublisher, get_log_publisher, set_log_publisher
from workflow.routing import route_after_risk_guard, route_after_risk_guard_mapping

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()


def _emit_flow(repo: FlowEventRepo | None, event: FlowEvent) -> None:
    if repo:
        repo.emit(event)


def _reasoning_entry(
    *,
    node: str,
    thought: str,
    decision: Any | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Unified reasoning payload for state + FlowEvent."""
    detail = thought.strip() if isinstance(thought, str) else str(thought)
    return {
        "node": node,
        "reasoning_chain": detail,
        "thought_process": detail,
        "decision": decision,
        "extra": extra or {},
    }


NodeFn = Callable[[HedgeFundState], dict[str, Any]]


def _instrument_node(node_name: str, node_fn: NodeFn) -> NodeFn:
    """Wrap graph nodes with start/end + reasoning telemetry."""

    def wrapped(state: HedgeFundState) -> dict[str, Any]:
        repo = get_flow_repo()
        run_id = getattr(repo, "run_id", None) if repo else None
        _emit_flow(
            repo,
            FlowEvent.node_start(node_name, run_id=run_id, ticker=state.get("ticker")),
        )
        try:
            out = node_fn(state)
        except Exception as e:
            _emit_flow(
                repo,
                FlowEvent.node_end(
                    node_name,
                    run_id=run_id,
                    summary="error",
                    error=str(e),
                ),
            )
            raise

        output_keys = list(out.keys())
        _emit_flow(
            repo,
            FlowEvent.node_end(
                node_name,
                run_id=run_id,
                summary="ok",
                output_keys=output_keys,
            ),
        )
        for entry in out.get("reasoning_logs") or []:
            _emit_flow(
                repo,
                FlowEvent.reasoning(
                    agent=str(entry.get("node", node_name)),
                    role="agent",
                    thought=str(entry.get("thought_process", "")),
                    decision=entry.get("decision"),
                    run_id=run_id,
                    node=node_name,
                ),
            )
        return out

    return wrapped


def _final_state_summary(state: HedgeFundState) -> dict[str, Any]:
    """Compact summary for INFO logs."""
    market_data = state.get("market_data") or {}
    market_context = state.get("market_context") or []
    reasoning_logs = state.get("reasoning_logs") or []
    risk_report = state.get("risk_report") or {}
    execution_result = state.get("execution_result") or {}
    proposal = state.get("proposal") or {}
    return {
        "ticker": state.get("ticker"),
        "run_mode": state.get("run_mode"),
        "is_vetoed": state.get("is_vetoed"),
        "veto_reason": state.get("veto_reason"),
        "risk_status": risk_report.get("status"),
        "execution_status": execution_result.get("status"),
        "proposal_status": proposal.get("status"),
        "market_symbols_count": len(market_data),
        "market_context_count": len(market_context),
        "reasoning_logs_count": len(reasoning_logs),
    }


def market_scan(state: HedgeFundState) -> dict[str, Any]:
    logger.debug("Running market_scan node with state: %s", state)
    ticker = state.get("ticker")
    if not ticker or not isinstance(ticker, str):
        logger.error("Invalid or missing ticker, using default BTC/USDT")
        ticker = "BTC/USDT"

    agent = MarketScanAgent(testnet=True)
    data = dict(state.get("market_data") or {})
    try:
        data[ticker] = agent.fetch_data(ticker)
        logger.debug("Fetched data for %s: %s", ticker, data[ticker])
    except Exception as e:
        logger.error("Failed to fetch data for %s: %s", ticker, e)
        data[ticker] = {"status": "error", "error": str(e)}

    meme_coins = agent.scan_meme_coins()
    for coin in meme_coins[:2]:
        if coin["symbol"] in agent.exchange.markets:
            try:
                data[coin["symbol"]] = agent.fetch_data(coin["symbol"])
            except Exception as e:
                logger.error("Failed to fetch data for %s: %s", coin["symbol"], e)
                data[coin["symbol"]] = {"status": "error", "error": str(e)}

    return {
        "ticker": ticker,
        "market_data": data,
        "market_scan": meme_coins,
        "market_context": [
            {
                "node": "market_scan",
                "ticker": ticker,
                "symbols": list(data.keys())[:8],
            }
        ],
        "reasoning_logs": [
            _reasoning_entry(
                node="market_scan",
                thought=(
                    f"Scanned {len(data)} symbols and identified {len(meme_coins)} meme candidates."
                ),
                decision={"symbols": len(data), "meme_candidates": len(meme_coins)},
            )
        ],
    }


def price_pattern(state: HedgeFundState) -> dict[str, Any]:
    logger.debug("Running price_pattern node with state: %s", state)
    ticker = state.get("ticker", "BTC/USDT")
    market_data = state.get("market_data") or {}
    agent = PricePatternAgent()
    analysis = agent.analyze(ticker, market_data)
    return {
        "pattern_analysis": analysis,
        "market_context": [{"node": "price_pattern", "analysis": analysis}],
        "reasoning_logs": [
            _reasoning_entry(
                node="price_pattern",
                thought="Technical pattern analysis completed for primary ticker.",
                decision=analysis,
            )
        ],
    }


def sentiment(state: HedgeFundState) -> dict[str, Any]:
    logger.debug("Running sentiment node with state: %s", state)
    ticker = state.get("ticker", "BTC/USDT")
    agent = SentimentAgent()
    analysis = agent.analyze(ticker)
    return {
        "sentiment_analysis": analysis,
        "market_context": [{"node": "sentiment", "analysis": analysis}],
        "reasoning_logs": [
            _reasoning_entry(
                node="sentiment",
                thought="Sentiment scan completed from social/news signals.",
                decision=analysis,
            )
        ],
    }


def stat_arb(state: HedgeFundState) -> dict[str, Any]:
    logger.debug("Running stat_arb node with state: %s", state)
    market_data = state.get("market_data") or {}
    market_scan = state.get("market_scan") or []
    agent = StatArbAgent()
    analysis = agent.analyze(market_data, market_scan)
    return {
        "arb_analysis": analysis,
        "market_context": [{"node": "stat_arb", "analysis": analysis}],
        "reasoning_logs": [
            _reasoning_entry(
                node="stat_arb",
                thought="Pair and spread opportunities evaluated.",
                decision=analysis,
            )
        ],
    }


def quant(state: HedgeFundState) -> dict[str, Any]:
    logger.debug("Running quant node with state: %s", state)
    market_data = state.get("market_data") or {}
    agent = QuantAgent()
    analysis = agent.analyze(market_data)
    return {
        "quant_analysis": analysis,
        "market_context": [{"node": "quant", "analysis": analysis}],
        "reasoning_logs": [
            _reasoning_entry(
                node="quant",
                thought="Momentum and quant indicators computed.",
                decision=analysis,
            )
        ],
    }


def valuation(state: HedgeFundState) -> dict[str, Any]:
    logger.debug("Running valuation node with state: %s", state)
    market_data = state.get("market_data") or {}
    market_scan = state.get("market_scan") or []
    agent = ValuationAgent()
    analysis = agent.analyze(market_data, market_scan)
    return {
        "valuation": analysis,
        "market_context": [{"node": "valuation", "analysis": analysis}],
        "reasoning_logs": [
            _reasoning_entry(
                node="valuation",
                thought="Relative valuation baseline computed.",
                decision=analysis,
            )
        ],
    }


def liquidity(state: HedgeFundState) -> dict[str, Any]:
    logger.debug("Running liquidity node with state: %s", state)
    market_data = state.get("market_data") or {}
    agent = LiquidityManagementAgent()
    analysis = agent.analyze(market_data)
    return {
        "liquidity": analysis,
        "market_context": [{"node": "liquidity", "analysis": analysis}],
        "reasoning_logs": [
            _reasoning_entry(
                node="liquidity",
                thought="Liquidity and depth profile calculated.",
                decision=analysis,
            )
        ],
    }


def risk(state: HedgeFundState) -> dict[str, Any]:
    logger.debug("Running risk node with state: %s", state)
    market_data = state.get("market_data") or {}
    valuation_data = state.get("valuation") or {}
    agent = RiskManagementAgent()
    risk_out = agent.analyze(market_data, valuation_data)
    return {
        "risk": risk_out,
        "reasoning_logs": [
            _reasoning_entry(
                node="risk",
                thought="Risk profile generated from market and valuation context.",
                decision=risk_out,
            )
        ],
    }


def _run_async(coro):
    """
    Run async code from a sync LangGraph node.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()
    return asyncio.run(coro)


def portfolio_proposal(state: HedgeFundState) -> dict[str, Any]:
    logger.debug("Running portfolio_proposal node with state: %s", state)
    agent = PortfolioManagementAgent(testnet=True)
    proposal = agent.analyze(
        state.get("ticker", "BTC/USDT"),
        state.get("market_data") or {},
        state.get("pattern_analysis") or {},
        state.get("sentiment_analysis") or {},
        state.get("arb_analysis") or {},
        state.get("quant_analysis") or {},
        state.get("valuation") or {},
        state.get("risk") or {},
        state.get("liquidity") or {},
        execute=False,
    )
    prop = proposal if isinstance(proposal, dict) else {}
    return {
        "proposal": proposal,
        "proposed_signal": prop,
        "reasoning_logs": [
            _reasoning_entry(
                node="portfolio_proposal",
                thought="Portfolio desk created a proposal from Tier-1 + risk inputs.",
                decision=prop,
            )
        ],
    }


def risk_guard(state: HedgeFundState) -> dict[str, Any]:
    logger.debug("Running risk_guard node with state: %s", state)
    repo = get_flow_repo()
    run_id = getattr(repo, "run_id", None) if repo else None

    guard = RiskGuardAgent()
    decision = _run_async(guard.process(state.get("proposal") or {}))
    reasoning = decision.get("reasoning") or {}
    is_vetoed = decision.get("status") == "VETOED"
    veto_reason = ""
    if is_vetoed:
        veto_reason = str(reasoning.get("thought") or decision.get("status", "VETOED"))

    out: dict[str, Any] = {
        "risk_guard": decision,
        "risk_report": decision,
        "is_vetoed": is_vetoed,
        "veto_reason": veto_reason,
        "proposed_signal": state.get("proposal") or {},
        "reasoning_logs": [
            {
                "node": "risk_guard",
                "status": decision.get("status"),
                "risk_score": decision.get("risk_score"),
                "thought_process": reasoning.get("thought"),
            }
        ],
    }
    if is_vetoed:
        out["execution_result"] = {
            "status": "skipped",
            "message": "Execution vetoed by Risk Guard",
            "risk_guard": decision,
        }

    _emit_flow(
        repo,
        FlowEvent.risk_guard(
            status=str(decision.get("status", "APPROVED")),
            risk_score=float(decision.get("risk_score", 0.0)),
            reasoning=reasoning if isinstance(reasoning, dict) else {"raw": reasoning},
            run_id=run_id,
        ),
    )

    pub = get_log_publisher()
    if pub:
        thought_process = [
            {"step": 1, "label": "Risk check", "detail": reasoning.get("thought", str(decision))}
        ]
        veto_status = {
            "checked_by": "risk-guard",
            "status": decision.get("status", "APPROVED"),
            "reason": reasoning.get("thought"),
        }
        proposal = state.get("proposal") or {}
        prop = None
        if isinstance(proposal, dict) and proposal.get("trades"):
            prop = {"action": "PROPOSAL", "params": proposal}
        pub.publish(
            actor_id="risk-guard",
            role=guard.role,
            thought_process=thought_process,
            context={"pair": state.get("ticker"), "signal": None, "confidence": None},
            proposal=prop,
            veto_status=veto_status,
            persona_ref="docs/personas/08_risk_guard.md",
        )

    logger.debug("risk_guard output: %s", out)
    return out


def portfolio_execute(state: HedgeFundState) -> dict[str, Any]:
    logger.debug("Running portfolio_execute node with state: %s", state)
    repo = get_flow_repo()
    run_id = getattr(repo, "run_id", None) if repo else None

    if state.get("is_vetoed"):
        logger.warning("portfolio_execute reached while vetoed; skipping (routing bug?)")
        return {}

    agent = PortfolioManagementAgent(testnet=True)
    portfolio_result = agent.analyze(
        state.get("ticker", "BTC/USDT"),
        state.get("market_data") or {},
        state.get("pattern_analysis") or {},
        state.get("sentiment_analysis") or {},
        state.get("arb_analysis") or {},
        state.get("quant_analysis") or {},
        state.get("valuation") or {},
        state.get("risk") or {},
        state.get("liquidity") or {},
        execute=True,
    )
    out = {
        "portfolio": portfolio_result,
        "execution_result": {
            "status": "executed",
            "portfolio": portfolio_result,
        },
        "reasoning_logs": [
            _reasoning_entry(
                node="portfolio_execute",
                thought="Execution desk placed approved orders.",
                decision=portfolio_result,
            )
        ],
    }
    pk = list(portfolio_result.keys()) if isinstance(portfolio_result, dict) else []
    _emit_flow(
        repo,
        FlowEvent.execution(
            status="executed",
            run_id=run_id,
            message="Portfolio execution completed",
            extra={"portfolio_keys": pk},
        ),
    )
    logger.debug("portfolio_execute output: %s", out)
    return out


def validate_ticker(ticker: str) -> bool:
    """Check if ticker is valid on Binance Testnet."""
    try:
        exchange = ccxt.binance(
            {
                "apiKey": os.getenv("BINANCE_API_KEY"),
                "secret": os.getenv("BINANCE_API_SECRET"),
                "enableRateLimit": True,
            }
        )
        exchange.set_sandbox_mode(True)
        exchange.load_markets()
        return ticker in exchange.markets
    except Exception as e:
        logger.error("Error validating ticker %s: %s", ticker, e)
        return False


def build_workflow() -> StateGraph:
    """Compile LangGraph: serial perception → proposal → risk → conditional execution.

    Node IDs are prefixed with ``desk_`` where needed so they do not collide with
    :class:`HedgeFundState` keys (LangGraph requirement).
    """
    workflow: StateGraph = StateGraph(HedgeFundState)
    workflow.add_node("desk_market_scan", _instrument_node("market_scan", market_scan))
    workflow.add_node("price_pattern", _instrument_node("price_pattern", price_pattern))
    workflow.add_node("sentiment", _instrument_node("sentiment", sentiment))
    workflow.add_node("stat_arb", _instrument_node("stat_arb", stat_arb))
    workflow.add_node("quant", _instrument_node("quant", quant))
    workflow.add_node("desk_valuation", _instrument_node("valuation", valuation))
    workflow.add_node("desk_liquidity", _instrument_node("liquidity", liquidity))
    workflow.add_node("desk_risk", _instrument_node("risk", risk))
    workflow.add_node(
        "portfolio_proposal",
        _instrument_node("portfolio_proposal", portfolio_proposal),
    )
    workflow.add_node("desk_risk_guard", _instrument_node("risk_guard", risk_guard))
    workflow.add_node(
        "portfolio_execute",
        _instrument_node("portfolio_execute", portfolio_execute),
    )

    workflow.set_entry_point("desk_market_scan")
    tier1_nodes = [
        "price_pattern",
        "sentiment",
        "stat_arb",
        "quant",
        "desk_valuation",
        "desk_liquidity",
    ]
    for node_id in tier1_nodes:
        workflow.add_edge("desk_market_scan", node_id)
        workflow.add_edge(node_id, "desk_risk")
    workflow.add_edge("desk_risk", "portfolio_proposal")
    workflow.add_edge("portfolio_proposal", "desk_risk_guard")
    path_map = route_after_risk_guard_mapping()
    workflow.add_conditional_edges("desk_risk_guard", route_after_risk_guard, path_map)
    workflow.add_edge("portfolio_execute", END)

    return workflow


def main():
    parser = argparse.ArgumentParser(description="AI Market Maker")
    parser.add_argument("--ticker", type=str, default="BTC/USDT", help="Trading pair")
    parser.add_argument(
        "--mode",
        type=str,
        choices=[m.value for m in RunMode],
        default=None,
        help=(
            "Execution mode (overrides MODE env). Default: paper. "
            "Live requires AI_MARKET_MAKER_ALLOW_LIVE=1."
        ),
    )
    args = parser.parse_args()

    run_mode = load_run_mode(override=args.mode)
    logger.info("Run mode: %s", run_mode.value)

    if not args.ticker or not validate_ticker(args.ticker):
        logger.error("Invalid ticker: %s", args.ticker)
        raise ValueError(
            f"Invalid ticker: {args.ticker}. Use a valid Binance Testnet pair (e.g., BTC/USDT)."
        )

    state = initial_hedge_fund_state(run_mode=run_mode.value, ticker=args.ticker)
    logger.debug("Initial state: %s", state)

    run_id = f"run-{args.ticker.replace('/', '-')}-{int(time.time())}"
    publisher = LogPublisher(run_id=run_id)
    set_log_publisher(publisher)
    flow_repo = FlowEventRepo(run_id=run_id)
    set_flow_repo(flow_repo)

    app = build_workflow().compile()
    try:
        result = app.invoke(state)
        logger.info("Run completed: %s", _final_state_summary(result))
        logger.debug("Final state (full): %s", pformat(result, compact=True))
    except Exception as e:
        logger.error("Workflow error: %s", e)
        raise
    finally:
        set_flow_repo(None)


if __name__ == "__main__":
    main()
