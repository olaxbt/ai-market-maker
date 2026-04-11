import argparse
import asyncio
import logging
import os
import time
from pathlib import Path
from pprint import pformat
from typing import Any, Callable

import ccxt
from dotenv import load_dotenv
from langgraph.graph import END, StateGraph

from adapters.nexus_adapter import get_nexus_adapter
from agents.governance.policy_orchestrator import PolicyOrchestratorAgent
from agents.governance.risk_guard import RiskGuardAgent
from agents.liquidity_order_flow import LiquidityOrderFlowAgent
from agents.market_scan import MarketScanAgent
from agents.monetary_sentinel import MonetarySentinelAgent
from agents.news_narrative_miner import NewsNarrativeMinerAgent
from agents.pattern_recognition_bot import PatternRecognitionBotAgent
from agents.portfolio_management import PortfolioManagementAgent
from agents.pro_bias_analyst import ProBiasAnalystAgent
from agents.retail_hype_tracker import RetailHypeTrackerAgent
from agents.risk_management import RiskManagementAgent
from agents.statistical_alpha_engine import StatisticalAlphaEngineAgent
from agents.technical_ta_engine import TechnicalTaEngineAgent
from agents.whale_behavior_analyst import WhaleBehaviorAnalystAgent
from config.app_settings import load_app_settings
from config.llm_env import use_llm_arbitrator
from config.llm_mode import llm_mode_enabled
from config.run_mode import RunMode, load_run_mode
from flow_log import FlowEventRepo, get_flow_repo, set_flow_repo
from llm.arbitrator_llm import signal_arbitrator_llm
from llm.portfolio_llm import llm_portfolio_execute, llm_portfolio_proposal
from market.universe import augment_universe_with_oi, select_universe_from_tickers
from nexus_data.client import NexusDataClient
from nexus_data.feeds import (
    fetch_nexus_global_bundle,
    fetch_nexus_per_symbol,
    merge_bundle_with_per_symbol,
    nexus_feeds_enabled,
    oi_ccxt_candidates,
)
from schemas.flow_events import FlowEvent
from schemas.state import HedgeFundState, initial_hedge_fund_state
from schemas.tier0_contract import build_tier0_contract_json
from telemetry.logger import LogPublisher, get_log_publisher, set_log_publisher
from tier1 import apply_strategy, effective_portfolio_desk_bridge, load_tier1_blueprint_from_env
from tier1.signal_params import build_tier1_proposed_params
from trading.desk_inputs import quant_analysis_for_portfolio
from workflow.arbitrator_shadow import backtest_momentum_score_delta
from workflow.desk_debate import desk_debate
from workflow.execution_intent import derive_trade_intent
from workflow.routing import route_after_risk_guard, route_after_risk_guard_mapping
from workflow.tier2_context import build_synthesis_board, compute_legacy_arbitrator_scores

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# Always let `.env` win over inherited shell env (including empty values).
load_dotenv(override=True)


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


def _tier0_nexus_context(state: HedgeFundState) -> dict[str, Any] | None:
    sm = state.get("shared_memory")
    if not isinstance(sm, dict):
        return None
    nx = sm.get("nexus")
    return nx if isinstance(nx, dict) else None


def _flow_bt_extra(state: HedgeFundState) -> dict[str, Any]:
    """Attach synthetic bar step/time to FlowEvents during backtest (for UI timelines)."""
    sm = state.get("shared_memory")
    if not isinstance(sm, dict):
        return {}
    bt = sm.get("backtest")
    if not isinstance(bt, dict):
        return {}
    out: dict[str, Any] = {}
    if "step" in bt:
        out["bar_step"] = bt["step"]
    if "run_id" in bt:
        out["backtest_run_id"] = bt["run_id"]
    ticker = state.get("ticker")
    md = state.get("market_data") or {}
    if isinstance(ticker, str) and isinstance(md, dict):
        pair = md.get(ticker)
        if isinstance(pair, dict):
            ohlcv = pair.get("ohlcv")
            if isinstance(ohlcv, list) and ohlcv:
                last = ohlcv[-1]
                if isinstance(last, (list, tuple)) and len(last) > 0:
                    try:
                        ts_ms = float(last[0])
                        out["bar_ts_ms"] = ts_ms
                        out["bar_time_utc"] = time.strftime(
                            "%Y-%m-%d %H:%M UTC",
                            time.gmtime(ts_ms / 1000.0),
                        )
                    except (TypeError, ValueError, OSError):
                        pass
    return out


def _instrument_node(node_name: str, node_fn: NodeFn) -> NodeFn:
    """Wrap graph nodes with start/end + reasoning telemetry."""

    def wrapped(state: HedgeFundState) -> dict[str, Any]:
        repo = get_flow_repo()
        run_id = getattr(repo, "run_id", None) if repo else None
        bt_x = _flow_bt_extra(state)
        _emit_flow(
            repo,
            FlowEvent.node_start(node_name, run_id=run_id, ticker=state.get("ticker"), **bt_x),
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
                    **bt_x,
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
                **bt_x,
            ),
        )
        for entry in out.get("reasoning_logs") or []:
            flow_extra: dict[str, Any] = dict(bt_x)
            ent_ex = entry.get("extra")
            if isinstance(ent_ex, dict) and ent_ex:
                flow_extra = {**ent_ex, **flow_extra}
            _emit_flow(
                repo,
                FlowEvent.reasoning(
                    agent=str(entry.get("node", node_name)),
                    role="agent",
                    thought=str(entry.get("thought_process", "")),
                    decision=entry.get("decision"),
                    run_id=run_id,
                    node=node_name,
                    **flow_extra,
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

    data = dict(state.get("market_data") or {})
    run_mode = str(state.get("run_mode") or "paper").lower()
    s = load_app_settings()
    desired_universe_size = int(s.market.universe_size)
    requested = list(s.market.universe_symbols)

    sm_out = dict(state.get("shared_memory") or {})

    if run_mode == RunMode.BACKTEST.value:
        # Backtest mode must be deterministic and offline-friendly.
        meme_coins: list[dict[str, Any]] = []
        if ticker not in data:
            data[ticker] = {"status": "backtest", "note": "no market_data provided"}
        universe = requested or list(data.keys()) or [ticker]
        universe = [ticker] + [s for s in universe if s != ticker]
        universe = universe[: max(1, desired_universe_size)]
        pairs = [
            [a, b]
            for a, b in select_universe_from_tickers(None, primary=ticker, size=len(universe)).pairs
        ]
        scan_decision: dict[str, Any] = {"symbols": len(data), "meme_candidates": len(meme_coins)}
    else:
        agent = MarketScanAgent(testnet=True)
        markets_keys = set(agent.exchange.markets.keys())
        tickers = None
        try:
            tickers = agent.exchange.fetch_tickers()
        except Exception:
            tickers = None
        try:
            data[ticker] = agent.fetch_data(ticker)
            logger.debug("Fetched data for %s: %s", ticker, data[ticker])
        except Exception as e:
            logger.error("Failed to fetch data for %s: %s", ticker, e)
            data[ticker] = {"status": "error", "error": str(e)}

        try:
            data[ticker]["nexus_depth"] = get_nexus_adapter().fetch_market_depth(
                symbol=ticker,
                limit=5,
            )
        except Exception as e:
            data[ticker]["nexus_depth"] = {"status": "error", "error": str(e)}

        meme_coins = agent.scan_meme_coins()
        for coin in meme_coins[:2]:
            if coin["symbol"] in agent.exchange.markets:
                try:
                    data[coin["symbol"]] = agent.fetch_data(coin["symbol"])
                except Exception as e:
                    logger.error("Failed to fetch data for %s: %s", coin["symbol"], e)
                    data[coin["symbol"]] = {"status": "error", "error": str(e)}

        nexus_bundle: dict[str, Any] | None = None
        nxc: NexusDataClient | None = None
        gb: dict[str, Any] = {}
        oi_ccxt: list[str] = []
        universe_source = "tickers_volume_rank"

        if nexus_feeds_enabled():
            try:
                nxc = NexusDataClient()
                gb = fetch_nexus_global_bundle(nxc)
                oi_ccxt = oi_ccxt_candidates(gb)
            except Exception as e:
                logger.warning("Nexus global feeds failed: %s", e)
                gb = {"endpoints": {}, "errors": [str(e)], "fetched_at_epoch": time.time()}
                oi_ccxt = []

        if requested:
            universe = [ticker] + [s for s in requested if s != ticker]
            universe = universe[: max(1, desired_universe_size)]
            pairs = [[a, b] for i, a in enumerate(universe) for b in universe[i + 1 :]][:21]
            universe_source = "env_aimm_universe"
        else:
            sel = augment_universe_with_oi(
                oi_ccxt,
                primary=ticker,
                tickers=tickers,
                size=max(1, desired_universe_size),
                markets=markets_keys,
            )
            universe = sel.universe
            pairs = [[a, b] for a, b in sel.pairs]
            universe_source = sel.source

        for sym in universe:
            if sym not in data and sym in markets_keys:
                try:
                    data[sym] = agent.fetch_data(sym)
                except Exception as e:
                    logger.error("Failed to fetch data for %s: %s", sym, e)
                    data[sym] = {"status": "error", "error": str(e)}
            blob = data.get(sym)
            if isinstance(blob, dict) and "nexus_depth" not in blob and sym in markets_keys:
                try:
                    blob["nexus_depth"] = get_nexus_adapter().fetch_market_depth(
                        symbol=sym, limit=5
                    )
                except Exception as e:
                    blob["nexus_depth"] = {"status": "error", "error": str(e)}

        if nexus_feeds_enabled():
            if nxc is not None:
                try:
                    per = fetch_nexus_per_symbol(nxc, universe)
                    nexus_bundle = merge_bundle_with_per_symbol(gb, per)
                except Exception as e:
                    logger.warning("Nexus per-symbol feeds failed: %s", e)
                    merged_errs = list(gb.get("errors") or []) + [str(e)]
                    nexus_bundle = {**gb, "errors": merged_errs}
            else:
                nexus_bundle = gb if gb else None

        if nexus_bundle is not None:
            sm_out["nexus"] = nexus_bundle
            ne = len(nexus_bundle.get("errors") or [])
            if ne:
                logger.info("Nexus bundle attached with %d partial endpoint errors", ne)

        scan_decision = {
            "symbols": len(data),
            "meme_candidates": len(meme_coins),
            "universe_source": universe_source,
            "nexus_attached": nexus_bundle is not None,
        }

    return {
        "ticker": ticker,
        "universe": universe,
        "universe_pairs": pairs,
        "market_data": data,
        "market_scan": meme_coins,
        "shared_memory": sm_out,
        "market_context": [
            {
                "node": "market_scan",
                "ticker": ticker,
                "symbols": universe,
            }
        ],
        "reasoning_logs": [
            _reasoning_entry(
                node="market_scan",
                thought=(
                    f"Scanned {len(data)} symbols and identified {len(meme_coins)} meme candidates."
                    if run_mode != RunMode.BACKTEST.value
                    else f"Backtest mode: using provided market_data (symbols={len(data)})."
                ),
                decision=scan_decision,
            )
        ],
    }


def policy_orchestrator(state: HedgeFundState) -> dict[str, Any]:
    """Supervisor layer: select policy config/preset across runs (persistent memory)."""
    agent = PolicyOrchestratorAgent()
    out = _run_async(
        agent.process({"run_mode": state.get("run_mode"), "ticker": state.get("ticker")})
    )
    return {
        "policy_decision": out.get("policy_decision") if isinstance(out, dict) else {},
        "reasoning_logs": [
            _reasoning_entry(
                node="policy_orchestrator",
                thought=str(
                    (out.get("reasoning") or {}).get("thought")
                    if isinstance(out, dict)
                    else "Policy orchestrator ran."
                ),
                decision=out.get("policy_decision") if isinstance(out, dict) else {},
            )
        ],
    }


#
# Legacy Tier-0 agents (PricePatternAgent, SentimentAgent, StatArbAgent, QuantAgent,
# ValuationAgent, LiquidityManagementAgent) were removed in favor of AIMM8.
# Their corresponding node functions have been deleted to avoid keeping unused code.
#


def monetary_sentinel(state: HedgeFundState) -> dict[str, Any]:
    ticker = str(state.get("ticker") or "BTC/USDT")
    universe = state.get("universe") or [ticker]
    md = state.get("market_data") or {}
    nx = _tier0_nexus_context(state)
    agent = MonetarySentinelAgent()
    by_symbol = {
        sym: agent.analyze(ticker=sym, market_data=md, nexus_context=nx) for sym in universe
    }
    analysis = by_symbol.get(ticker) or {}
    return {
        "monetary_sentinel": {"primary": analysis, "by_symbol": by_symbol},
        "tier0_contracts": [build_tier0_contract_json("monetary_sentinel", analysis, ticker)],
        "market_context": [{"node": "monetary_sentinel", "analysis": analysis}],
        "reasoning_logs": [
            _reasoning_entry(
                node="monetary_sentinel",
                thought="Macro liquidity + systemic beta computed.",
                decision=analysis,
            )
        ],
    }


def news_narrative_miner(state: HedgeFundState) -> dict[str, Any]:
    ticker = str(state.get("ticker") or "BTC/USDT")
    universe = state.get("universe") or [ticker]
    md = state.get("market_data") or {}
    nx = _tier0_nexus_context(state)
    agent = NewsNarrativeMinerAgent()
    by_symbol = {
        sym: agent.analyze(ticker=sym, market_data=md, nexus_context=nx) for sym in universe
    }
    analysis = by_symbol.get(ticker) or {}
    return {
        "news_narrative_miner": {"primary": analysis, "by_symbol": by_symbol},
        "tier0_contracts": [build_tier0_contract_json("news_narrative_miner", analysis, ticker)],
        "market_context": [{"node": "news_narrative_miner", "analysis": analysis}],
        "reasoning_logs": [
            _reasoning_entry(
                node="news_narrative_miner",
                thought="News narrative miner evaluated systemic shock inputs.",
                decision=analysis,
            )
        ],
    }


def pattern_recognition_bot(state: HedgeFundState) -> dict[str, Any]:
    ticker = str(state.get("ticker") or "BTC/USDT")
    universe = state.get("universe") or [ticker]
    md = state.get("market_data") or {}
    nx = _tier0_nexus_context(state)
    agent = PatternRecognitionBotAgent()
    by_symbol = {
        sym: agent.analyze(ticker=sym, market_data=md, nexus_context=nx) for sym in universe
    }
    analysis = by_symbol.get(ticker) or {}
    return {
        "pattern_recognition_bot": {"primary": analysis, "by_symbol": by_symbol},
        "tier0_contracts": [build_tier0_contract_json("pattern_recognition_bot", analysis, ticker)],
        "market_context": [{"node": "pattern_recognition_bot", "analysis": analysis}],
        "reasoning_logs": [
            _reasoning_entry(
                node="pattern_recognition_bot",
                thought="Pattern recognition computed setup confidence and regime.",
                decision=analysis,
            )
        ],
    }


def statistical_alpha_engine(state: HedgeFundState) -> dict[str, Any]:
    ticker = str(state.get("ticker") or "BTC/USDT")
    universe = state.get("universe") or [ticker]
    md = state.get("market_data") or {}
    nx = _tier0_nexus_context(state)
    agent = StatisticalAlphaEngineAgent()
    by_symbol = {
        sym: agent.analyze(ticker=sym, market_data=md, nexus_context=nx) for sym in universe
    }
    analysis = by_symbol.get(ticker) or {}
    return {
        "statistical_alpha_engine": {"primary": analysis, "by_symbol": by_symbol},
        "tier0_contracts": [
            build_tier0_contract_json("statistical_alpha_engine", analysis, ticker)
        ],
        "market_context": [{"node": "statistical_alpha_engine", "analysis": analysis}],
        "reasoning_logs": [
            _reasoning_entry(
                node="statistical_alpha_engine",
                thought="Cross-sectional alpha engine executed (stubbed if no Nexus data).",
                decision=analysis,
            )
        ],
    }


def technical_ta_engine(state: HedgeFundState) -> dict[str, Any]:
    """Tier-0 Agent 2.3: OHLCV → TA-Lib bundle (``ta_*`` Tier-1 metric_ids)."""
    ticker = str(state.get("ticker") or "BTC/USDT")
    universe = state.get("universe") or [ticker]
    md = state.get("market_data") or {}
    agent = TechnicalTaEngineAgent()
    by_symbol = {sym: agent.analyze(ticker=sym, market_data=md) for sym in universe}
    analysis = by_symbol.get(ticker) or {}
    return {
        "technical_ta_engine": {"primary": analysis, "by_symbol": by_symbol},
        "tier0_contracts": [build_tier0_contract_json("technical_ta_engine", analysis, ticker)],
        "market_context": [{"node": "technical_ta_engine", "analysis": analysis}],
        "reasoning_logs": [
            _reasoning_entry(
                node="technical_ta_engine",
                thought="Classical TA bundle from OHLCV (Tier-0 contract 2.3).",
                decision=analysis,
            )
        ],
    }


def retail_hype_tracker(state: HedgeFundState) -> dict[str, Any]:
    ticker = str(state.get("ticker") or "BTC/USDT")
    universe = state.get("universe") or [ticker]
    md = state.get("market_data") or {}
    nx = _tier0_nexus_context(state)
    agent = RetailHypeTrackerAgent()
    by_symbol = {
        sym: agent.analyze(ticker=sym, market_data=md, nexus_context=nx) for sym in universe
    }
    analysis = by_symbol.get(ticker) or {}
    return {
        "retail_hype_tracker": {"primary": analysis, "by_symbol": by_symbol},
        "tier0_contracts": [build_tier0_contract_json("retail_hype_tracker", analysis, ticker)],
        "market_context": [{"node": "retail_hype_tracker", "analysis": analysis}],
        "reasoning_logs": [
            _reasoning_entry(
                node="retail_hype_tracker",
                thought="Retail hype and divergence evaluated (stubbed if no Nexus data).",
                decision=analysis,
            )
        ],
    }


def pro_bias_analyst(state: HedgeFundState) -> dict[str, Any]:
    ticker = str(state.get("ticker") or "BTC/USDT")
    universe = state.get("universe") or [ticker]
    md = state.get("market_data") or {}
    nx = _tier0_nexus_context(state)
    agent = ProBiasAnalystAgent()
    by_symbol = {
        sym: agent.analyze(ticker=sym, market_data=md, nexus_context=nx) for sym in universe
    }
    analysis = by_symbol.get(ticker) or {}
    return {
        "pro_bias_analyst": {"primary": analysis, "by_symbol": by_symbol},
        "tier0_contracts": [build_tier0_contract_json("pro_bias_analyst", analysis, ticker)],
        "market_context": [{"node": "pro_bias_analyst", "analysis": analysis}],
        "reasoning_logs": [
            _reasoning_entry(
                node="pro_bias_analyst",
                thought="Institutional flow regime evaluated (stubbed if no Nexus data).",
                decision=analysis,
            )
        ],
    }


def whale_behavior_analyst(state: HedgeFundState) -> dict[str, Any]:
    ticker = str(state.get("ticker") or "BTC/USDT")
    universe = state.get("universe") or [ticker]
    md = state.get("market_data") or {}
    nx = _tier0_nexus_context(state)
    agent = WhaleBehaviorAnalystAgent()
    by_symbol = {
        sym: agent.analyze(ticker=sym, market_data=md, nexus_context=nx) for sym in universe
    }
    analysis = by_symbol.get(ticker) or {}
    return {
        "whale_behavior_analyst": {"primary": analysis, "by_symbol": by_symbol},
        "tier0_contracts": [build_tier0_contract_json("whale_behavior_analyst", analysis, ticker)],
        "market_context": [{"node": "whale_behavior_analyst", "analysis": analysis}],
        "reasoning_logs": [
            _reasoning_entry(
                node="whale_behavior_analyst",
                thought="Whale behavior and supply-shock risk evaluated (stubbed if no Nexus data).",
                decision=analysis,
            )
        ],
    }


def liquidity_order_flow(state: HedgeFundState) -> dict[str, Any]:
    ticker = str(state.get("ticker") or "BTC/USDT")
    universe = state.get("universe") or [ticker]
    md = state.get("market_data") or {}
    nx = _tier0_nexus_context(state)
    agent = LiquidityOrderFlowAgent()
    by_symbol = {
        sym: agent.analyze(ticker=sym, market_data=md, nexus_context=nx) for sym in universe
    }
    analysis = by_symbol.get(ticker) or {}
    return {
        "liquidity_order_flow": {"primary": analysis, "by_symbol": by_symbol},
        "tier0_contracts": [build_tier0_contract_json("liquidity_order_flow", analysis, ticker)],
        "market_context": [{"node": "liquidity_order_flow", "analysis": analysis}],
        "reasoning_logs": [
            _reasoning_entry(
                node="liquidity_order_flow",
                thought="Liquidity/order-flow microstructure evaluated.",
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


def signal_arbitrator(state: HedgeFundState) -> dict[str, Any]:
    """Tier-2 synthesis: Tier-1 applier (if configured) else legacy scores from Tier-0 consensus + risk/sentiment.

    Preceding ``desk_debate`` appends human-readable rows to ``debate_transcript`` (deterministic + optional LLM).
    """
    legacy = compute_legacy_arbitrator_scores(state)
    debate_n = len(state.get("debate_transcript") or [])
    bull_score = int(legacy["bull_score"])
    bear_score = int(legacy["bear_score"])
    high_vol_assets = int(legacy["high_vol_assets"])
    sentiment_score = float(legacy["sentiment_score"])
    tc = legacy["tier0_consensus"]

    mb, ms, mnote = backtest_momentum_score_delta(state)
    bull_score += mb
    bear_score += ms

    tier1_blueprint = load_tier1_blueprint_from_env()
    if tier1_blueprint is not None:
        ep = apply_strategy(
            state,
            tier1_blueprint,
            ticker=str(state.get("ticker") or "BTC/USDT"),
        )
        t1_params = build_tier1_proposed_params(
            ep,
            tier0_summary=str(tc.get("summary", "")),
            legacy_bull_score=bull_score,
            legacy_bear_score=bear_score,
        )
        t1_params["debate_entries"] = debate_n
        t1_params["reasons"] = [
            *(t1_params.get("reasons") or []),
            f"desk_debate_entries={debate_n}",
        ]
        proposed_signal = {
            "action": "PROPOSAL",
            "params": t1_params,
            "meta": {
                "source": "signal_arbitrator",
                "version": "v1_tier1",
            },
        }
    else:
        stance = "neutral"
        if bull_score > bear_score:
            stance = "bullish"
        elif bear_score > bull_score:
            stance = "bearish"

        confidence = round(min(0.95, 0.5 + (abs(bull_score - bear_score) * 0.15)), 2)
        if stance != "neutral":
            confidence = max(0.55, confidence)
        reasons = [
            f"bull_score={bull_score}",
            f"bear_score={bear_score}",
            f"sentiment={sentiment_score:.1f}",
            f"high_vol_assets={high_vol_assets}",
            f"tier0_consensus={tc.get('summary', '')}",
        ]
        reasons.append("stance_sources=risk+sentiment+tier0_contracts_legacy_scores")
        if mnote:
            reasons.append(mnote)
        reasons.append(f"desk_debate_entries={debate_n}")
        proposed_signal = {
            "action": "PROPOSAL",
            "params": {
                "stance": stance,
                "confidence": confidence,
                "reasons": reasons,
                "debate_entries": debate_n,
            },
            "meta": {
                "source": "signal_arbitrator",
                "version": "v1",
            },
        }
    board = build_synthesis_board(state)
    intent = derive_trade_intent(state, proposed_signal)
    return {
        "proposed_signal": proposed_signal,
        "trade_intent": intent,
        "reasoning_logs": [
            _reasoning_entry(
                node="signal_arbitrator",
                thought="Synthesized proposed_signal from Tier-1 applier or legacy Tier-0 consensus scores.",
                decision=proposed_signal,
                extra={"synthesis_board": board},
            ),
            _reasoning_entry(
                node="execution_intent",
                thought="Execution intent derived from thesis (deterministic stance → BUY/SELL/HOLD gate).",
                decision=intent,
            ),
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


def _portfolio_agent_kwargs(state: HedgeFundState) -> dict[str, Any]:
    """Pass simulated position qty into portfolio math during multi-step backtests."""
    sm = state.get("shared_memory")
    bt = sm.get("backtest") if isinstance(sm, dict) and isinstance(sm.get("backtest"), dict) else {}
    out: dict[str, Any] = {"run_mode": state.get("run_mode")}
    if str(state.get("run_mode") or "").lower() == RunMode.BACKTEST.value:
        out["external_cash_usd"] = float(bt.get("cash", 0.0))
        pos = bt.get("positions")
        if isinstance(pos, dict):
            ext_pos = {str(k): float(v) for k, v in pos.items()}
            uni = state.get("universe")
            if isinstance(uni, list):
                for sym in uni:
                    sk = str(sym)
                    if sk not in ext_pos:
                        ext_pos[sk] = 0.0
            out["external_positions"] = ext_pos
            ea = bt.get("entry_avg_by_symbol")
            entry_map = {str(k): float(v) for k, v in ea.items()} if isinstance(ea, dict) else {}
            if isinstance(uni, list):
                for sym in uni:
                    sk = str(sym)
                    if sk not in entry_map:
                        entry_map[sk] = 0.0
            out["external_entry_avg_by_symbol"] = entry_map
        else:
            out["external_position_qty"] = float(bt.get("qty", 0.0))
            out["external_entry_avg_price"] = float(bt.get("entry_avg_price", 0.0))
    return out


def merged_quant_analysis_for_universe(state: HedgeFundState) -> dict[str, Any]:
    """Per-symbol ``quant_analysis`` rows from Tier-0 ``by_symbol`` (multi-asset) or primary."""
    tk = str(state.get("ticker") or "BTC/USDT")
    uni = state.get("universe")
    symbols: list[str] = [str(x) for x in uni] if isinstance(uni, list) and uni else [tk]
    merged: dict[str, Any] = {}
    desk_bridge = effective_portfolio_desk_bridge()
    for sym in symbols:
        frag = quant_analysis_for_portfolio(state, sym, desk_bridge=desk_bridge)
        an = frag.get("analysis") if isinstance(frag, dict) else None
        row = an.get(sym) if isinstance(an, dict) else None
        if isinstance(row, dict):
            merged[sym] = row
    return {"status": "success", "analysis": merged}


def portfolio_proposal(state: HedgeFundState) -> dict[str, Any]:
    logger.debug("Running portfolio_proposal node with state: %s", state)
    tk = state.get("ticker", "BTC/USDT")
    if llm_mode_enabled():
        proposal = llm_portfolio_proposal(state)
        # Fallback if provider/model is misconfigured or output invalid.
        if not isinstance(proposal, dict) or proposal.get("status") == "error":
            logger.warning("LLM portfolio_proposal failed; falling back to deterministic agent.")
            agent = PortfolioManagementAgent(testnet=True)
            proposal = agent.analyze(
                tk,
                state.get("market_data") or {},
                state.get("pattern_analysis") or {},
                state.get("sentiment_analysis") or {},
                state.get("arb_analysis") or {},
                merged_quant_analysis_for_universe(state),
                state.get("valuation") or {},
                state.get("risk") or {},
                state.get("liquidity") or {},
                execute=False,
                strategy_context=state.get("proposed_signal") or {},
                trade_intent=state.get("trade_intent") or {},
                **_portfolio_agent_kwargs(state),
            )
    else:
        agent = PortfolioManagementAgent(testnet=True)
        proposal = agent.analyze(
            tk,
            state.get("market_data") or {},
            state.get("pattern_analysis") or {},
            state.get("sentiment_analysis") or {},
            state.get("arb_analysis") or {},
            merged_quant_analysis_for_universe(state),
            state.get("valuation") or {},
            state.get("risk") or {},
            state.get("liquidity") or {},
            execute=False,
            strategy_context=state.get("proposed_signal") or {},
            trade_intent=state.get("trade_intent") or {},
            **_portfolio_agent_kwargs(state),
        )
    prop = proposal if isinstance(proposal, dict) else {}
    signal_context = state.get("proposed_signal") or {}
    if isinstance(prop, dict):
        prop["strategy_context"] = signal_context
    return {
        "proposal": proposal,
        "proposed_signal": {
            "action": "PROPOSAL",
            "params": prop,
            "meta": {
                "source": "portfolio_proposal",
                "upstream_signal": signal_context,
            },
        },
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
    decision = _run_async(
        guard.process(
            {
                "proposal": state.get("proposal") or {},
                "shared_memory": state.get("shared_memory") or {},
                "ticker": state.get("ticker"),
                "run_mode": state.get("run_mode"),
            }
        )
    )
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
        "proposed_signal": state.get("proposed_signal") or {},
        "reasoning_logs": [
            _reasoning_entry(
                node="risk_guard",
                thought=str(reasoning.get("thought") or "Risk guard completed."),
                decision={
                    "status": decision.get("status"),
                    "risk_score": decision.get("risk_score"),
                },
            )
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
            **_flow_bt_extra(state),
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

    # For safety + tool-calling parity, treat this node as "execution intent" and place via adapter.
    tk = state.get("ticker", "BTC/USDT")
    if llm_mode_enabled():
        # Prefer the proposal from the previous node if present.
        portfolio_result = state.get("proposal")
        if not isinstance(portfolio_result, dict):
            portfolio_result = llm_portfolio_proposal(state)
        exec_blk = llm_portfolio_execute(
            state, portfolio_result=portfolio_result if isinstance(portfolio_result, dict) else {}
        )
        if not isinstance(exec_blk, dict) or exec_blk.get("status") in ("error",):
            logger.warning("LLM portfolio_execute failed; falling back to deterministic agent.")
            agent = PortfolioManagementAgent(testnet=True)
            portfolio_result = agent.analyze(
                tk,
                state.get("market_data") or {},
                state.get("pattern_analysis") or {},
                state.get("sentiment_analysis") or {},
                state.get("arb_analysis") or {},
                merged_quant_analysis_for_universe(state),
                state.get("valuation") or {},
                state.get("risk") or {},
                state.get("liquidity") or {},
                execute=False,
                strategy_context=state.get("proposed_signal") or {},
                trade_intent=state.get("trade_intent") or {},
                **_portfolio_agent_kwargs(state),
            )
            exec_blk = None
    else:
        agent = PortfolioManagementAgent(testnet=True)
        portfolio_result = agent.analyze(
            tk,
            state.get("market_data") or {},
            state.get("pattern_analysis") or {},
            state.get("sentiment_analysis") or {},
            state.get("arb_analysis") or {},
            merged_quant_analysis_for_universe(state),
            state.get("valuation") or {},
            state.get("risk") or {},
            state.get("liquidity") or {},
            execute=False,
            strategy_context=state.get("proposed_signal") or {},
            trade_intent=state.get("trade_intent") or {},
            **_portfolio_agent_kwargs(state),
        )
        exec_blk = None

    # P3: emit a safe "smart order" record via NexusAdapter (mock by default).
    # This does not place a real order yet; it provides tool-calling parity for the UI.
    smart_orders: list[dict[str, Any]] = []
    adapter = get_nexus_adapter()
    if llm_mode_enabled() and isinstance(exec_blk, dict):
        for row in exec_blk.get("smart_orders") or []:
            if not isinstance(row, dict):
                continue
            sym = str(row.get("symbol") or "")
            side = str(row.get("side") or "").lower()
            qty = float(row.get("qty") or 0.0)
            if sym and side in ("buy", "sell") and qty > 0:
                smart_orders.append(
                    adapter.place_smart_order(
                        symbol=sym,
                        side=side,
                        qty=qty,
                        order_type="market",
                        post_only=True,
                        max_slippage_bps=25.0,
                    )
                )
    elif isinstance(portfolio_result, dict):
        trades = portfolio_result.get("trades") or {}
        for sym, trade in trades.items():
            if not isinstance(trade, dict) or trade.get("status") not in ("proposed", "success"):
                continue
            side = trade.get("action")
            qty = float(trade.get("quantity") or 0.0)
            if side in ("buy", "sell") and qty > 0:
                smart_orders.append(
                    adapter.place_smart_order(
                        symbol=str(sym),
                        side=side,
                        qty=qty,
                        order_type="market",
                        post_only=True,
                        max_slippage_bps=25.0,
                    )
                )
    smart_order = smart_orders[0] if smart_orders else None
    out = {
        "portfolio": portfolio_result
        if exec_blk is None
        else {**(portfolio_result or {}), "execution": exec_blk},
        "execution_result": {
            "status": "executed" if smart_orders else "skipped",
            "portfolio": portfolio_result
            if exec_blk is None
            else {**(portfolio_result or {}), "execution": exec_blk},
            "smart_order": smart_order,
            "smart_orders": smart_orders,
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
            extra={**{"portfolio_keys": pk}, **_flow_bt_extra(state)},
        ),
    )
    logger.debug("portfolio_execute output: %s", out)
    return out


def audit(state: HedgeFundState) -> dict[str, Any]:
    """Audit + persistent memory write of run outcome."""
    from memory.policy_memory import PolicyMemoryStore

    store = PolicyMemoryStore()
    event = {
        "kind": "run_end",
        "ticker": state.get("ticker"),
        "run_mode": state.get("run_mode"),
        "is_vetoed": bool(state.get("is_vetoed")),
        "veto_reason": state.get("veto_reason"),
        "execution_status": (state.get("execution_result") or {}).get("status"),
        "policy_decision": state.get("policy_decision") or {},
        "risk_guard": state.get("risk_guard") or {},
    }
    store.append_event(event)
    return {
        "reasoning_logs": [
            _reasoning_entry(
                node="audit",
                thought="Audit recorded run outcome to persistent memory.",
                decision={
                    "is_vetoed": event["is_vetoed"],
                    "execution_status": event["execution_status"],
                },
            )
        ]
    }


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
    workflow.add_node(
        "policy_orchestrator", _instrument_node("policy_orchestrator", policy_orchestrator)
    )
    workflow.add_node("desk_market_scan", _instrument_node("market_scan", market_scan))
    # Tier-0 AIMM8 perception layer.
    workflow.add_node("monetary_sentinel", _instrument_node("monetary_sentinel", monetary_sentinel))
    workflow.add_node(
        "news_narrative_miner",
        _instrument_node("news_narrative_miner", news_narrative_miner),
    )
    workflow.add_node(
        "pattern_recognition_bot",
        _instrument_node("pattern_recognition_bot", pattern_recognition_bot),
    )
    workflow.add_node(
        "statistical_alpha_engine",
        _instrument_node("statistical_alpha_engine", statistical_alpha_engine),
    )
    workflow.add_node(
        "technical_ta_engine",
        _instrument_node("technical_ta_engine", technical_ta_engine),
    )
    workflow.add_node(
        "retail_hype_tracker", _instrument_node("retail_hype_tracker", retail_hype_tracker)
    )
    workflow.add_node("pro_bias_analyst", _instrument_node("pro_bias_analyst", pro_bias_analyst))
    workflow.add_node(
        "whale_behavior_analyst", _instrument_node("whale_behavior_analyst", whale_behavior_analyst)
    )
    workflow.add_node(
        "liquidity_order_flow", _instrument_node("liquidity_order_flow", liquidity_order_flow)
    )
    workflow.add_node("desk_risk", _instrument_node("risk", risk))
    workflow.add_node("desk_debate", _instrument_node("desk_debate", desk_debate))
    arbitrator_fn = signal_arbitrator_llm if use_llm_arbitrator() else signal_arbitrator
    workflow.add_node("signal_arbitrator", _instrument_node("signal_arbitrator", arbitrator_fn))
    workflow.add_node(
        "portfolio_proposal",
        _instrument_node("portfolio_proposal", portfolio_proposal),
    )
    workflow.add_node("desk_risk_guard", _instrument_node("risk_guard", risk_guard))
    workflow.add_node(
        "portfolio_execute",
        _instrument_node("portfolio_execute", portfolio_execute),
    )
    workflow.add_node("audit", _instrument_node("audit", audit))

    workflow.set_entry_point("policy_orchestrator")
    tier0_nodes = [
        "monetary_sentinel",
        "news_narrative_miner",
        "pattern_recognition_bot",
        "statistical_alpha_engine",
        "technical_ta_engine",
        "retail_hype_tracker",
        "pro_bias_analyst",
        "whale_behavior_analyst",
        "liquidity_order_flow",
    ]
    workflow.add_edge("policy_orchestrator", "desk_market_scan")
    for node_id in tier0_nodes:
        workflow.add_edge("desk_market_scan", node_id)
        workflow.add_edge(node_id, "desk_risk")
    workflow.add_edge("desk_risk", "desk_debate")
    workflow.add_edge("desk_debate", "signal_arbitrator")
    workflow.add_edge("signal_arbitrator", "portfolio_proposal")
    workflow.add_edge("portfolio_proposal", "desk_risk_guard")
    path_map = route_after_risk_guard_mapping()
    workflow.add_conditional_edges("desk_risk_guard", route_after_risk_guard, path_map)
    workflow.add_edge("portfolio_execute", "audit")
    workflow.add_edge("audit", END)

    return workflow


def main():
    parser = argparse.ArgumentParser(description="AI Market Maker")
    _def_ticker = load_app_settings().market.default_ticker
    parser.add_argument(
        "--ticker",
        type=str,
        default=_def_ticker,
        help="Primary trading pair (default: config/app.default.json market.default_ticker).",
    )
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

    if run_mode is not RunMode.BACKTEST:
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
    runs_dir = Path(".runs")
    runs_dir.mkdir(parents=True, exist_ok=True)
    latest_file = runs_dir / "latest_run.txt"
    latest_file.write_text(run_id)
    flow_log_path = runs_dir / f"{run_id}.events.jsonl"
    if flow_log_path.exists():
        flow_log_path.unlink()
    flow_repo = FlowEventRepo(run_id=run_id, log_path=flow_log_path)
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
