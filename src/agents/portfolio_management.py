import json
import logging
import os
from typing import Any, Dict

import ccxt

from trading.policy_manager import PortfolioDecisionContext, TradingPolicyManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

# One ``load_markets()`` per (exchange, testnet): backtests invoke this agent every bar;
# without sharing, public Binance rate-limits (429) and long runs fail.
_CCXT_SHARED: dict[tuple[str, bool], Any] = {}


def _shared_ccxt_exchange(exchange: str, testnet: bool):
    key = (exchange, testnet)
    cached = _CCXT_SHARED.get(key)
    if cached is not None:
        return cached
    ex = getattr(ccxt, exchange)(
        {
            "apiKey": os.getenv("BINANCE_API_KEY"),
            "secret": os.getenv("BINANCE_API_SECRET"),
            "enableRateLimit": True,
        }
    )
    if testnet:
        ex.set_sandbox_mode(True)
    ex.load_markets()
    _CCXT_SHARED[key] = ex
    return ex


def _valid_tickers(market_data: Dict[str, Any]) -> list[str]:
    return [
        t
        for t in market_data
        if isinstance(market_data.get(t), dict)
        and market_data[t].get("status") in ("success", "backtest")
    ]


def _use_multi_asset_path(
    tickers: list[str],
    *,
    run_m: str,
    external_positions: Dict[str, float] | None,
) -> bool:
    """Hedge-fund default: size every symbol in ``market_data`` when there are 2+.

    Single-symbol **backtest** with a sim book uses ``external_positions`` dict (engine).
    """
    if len(tickers) >= 2:
        return True
    return run_m == "backtest" and isinstance(external_positions, dict)


class PortfolioManagementAgent:
    def __init__(self, exchange: str = "binance", testnet: bool = False):
        self.exchange = _shared_ccxt_exchange(exchange, testnet)
        self.positions_file = "positions.json"
        self._trading = TradingPolicyManager()
        self.load_positions()

    def load_positions(self):
        """Load current positions from file."""
        try:
            if os.path.exists(self.positions_file):
                with open(self.positions_file, "r") as f:
                    self.positions = json.load(f)
            else:
                self.positions = {}
        except Exception as e:
            logger.error(f"Error loading positions: {str(e)}")
            self.positions = {}

    def save_positions(self):
        """Save current positions to file."""
        try:
            with open(self.positions_file, "w") as f:
                json.dump(self.positions, f)
        except Exception as e:
            logger.error(f"Error saving positions: {str(e)}")

    def _multi_position_maps(
        self,
        tickers: list[str],
        *,
        run_m: str,
        external_positions: Dict[str, float] | None,
        external_entry_avg_by_symbol: Dict[str, float] | None,
    ) -> tuple[dict[str, float], dict[str, float]]:
        pos: dict[str, float] = {}
        ent: dict[str, float] = {}
        if run_m == "backtest":
            if isinstance(external_positions, dict):
                for sym in tickers:
                    pos[sym] = float(external_positions.get(sym, 0.0))
                    ent[sym] = float((external_entry_avg_by_symbol or {}).get(sym, 0.0))
                return pos, ent
            # Multi-symbol backtest without sim dict: flat book (engine should pass dict).
            for sym in tickers:
                pos[sym] = 0.0
                ent[sym] = 0.0
            return pos, ent

        self.load_positions()
        for sym in tickers:
            p = self.positions.get(sym)
            if isinstance(p, dict):
                pos[sym] = float(p.get("quantity") or 0.0)
                try:
                    ent[sym] = float(p.get("entry_price") or 0.0)
                except (TypeError, ValueError):
                    ent[sym] = 0.0
            else:
                pos[sym] = 0.0
                ent[sym] = 0.0
        return pos, ent

    def _build_multi_trades(
        self,
        tickers: list[str],
        *,
        market_data: Dict[str, Any],
        allocations: Dict[str, Any],
        quant_analysis: Dict[str, Any],
        arb_analysis: Dict[str, Any],
        sentiment_analysis: Dict[str, Any],
        trade_intent: Dict[str, Any] | None,
        run_m: str,
        external_cash_usd: float | None,
        pos_map: dict[str, float],
        entry_map: dict[str, float],
    ) -> Dict[str, Any]:
        action = str(
            trade_intent.get("action") if isinstance(trade_intent, dict) else "HOLD"
        ).upper()
        confidence = trade_intent.get("confidence") if isinstance(trade_intent, dict) else None
        conf_f = float(confidence) if isinstance(confidence, (int, float)) else 0.0
        sentiment_score = float(
            sentiment_analysis.get("sentiment_score") or sentiment_analysis.get("score") or 50.0
        )
        qa_inner = (
            quant_analysis.get("analysis")
            if isinstance(quant_analysis.get("analysis"), dict)
            else {}
        )
        trades: Dict[str, Any] = {}

        for sym in sorted(tickers):
            ohlcv_s = market_data.get(sym, {}).get("ohlcv", [])
            current_price = float(ohlcv_s[-1][4]) if ohlcv_s and len(ohlcv_s) > 0 else 0.0
            if current_price <= 0:
                trades[sym] = {"status": "skipped", "message": "Invalid price"}
                continue
            arb_signal = (
                (
                    arb_analysis.get("analysis")
                    if isinstance(arb_analysis.get("analysis"), dict)
                    else {}
                )
                .get(f"{sym}-*", {})
                .get("signal", "hold")
            )
            qtick = qa_inner.get(sym, {}) if isinstance(qa_inner.get(sym), dict) else {}
            quant_signal = (
                qtick.get("macd_signal", "hold") if qtick else quant_analysis.get("signal", "hold")
            )
            regime = qtick.get("ema_sma_regime") if isinstance(qtick, dict) else None
            portfolio_alloc = allocations.get(sym, {})
            target_amount = portfolio_alloc.get("amount", 0)
            target_quantity = target_amount / current_price if current_price > 0 else 0.0
            current_quantity = float(pos_map.get(sym, 0.0))
            entry_px = float(entry_map.get(sym, 0.0))
            ctx = PortfolioDecisionContext(
                ticker=sym,
                current_price=current_price,
                target_quantity=target_quantity,
                current_quantity=current_quantity,
                entry_avg_price=entry_px,
                run_mode=run_m,
                intent_action=action,
                intent_confidence=conf_f,
                sentiment_score=sentiment_score,
                quant_signal=str(quant_signal),
                arb_signal=str(arb_signal),
                ema_sma_regime=str(regime) if regime is not None else None,
                external_cash_usd=float(external_cash_usd)
                if external_cash_usd is not None
                else None,
            )
            trades[sym] = self._trading.decide(ctx)
        return trades

    def _execute_one_market_order(
        self, sym: str, trade_result: Dict[str, Any], current_price: float
    ) -> None:
        """Apply one proposed trade to the exchange and ``positions.json`` (paper/live)."""
        if not isinstance(trade_result, dict) or trade_result.get("status") != "proposed":
            return
        side = trade_result.get("action")
        qty = float(trade_result.get("quantity") or 0.0)
        if qty <= 1e-12:
            return
        position = self.positions.get(sym)
        has_position = isinstance(position, dict)
        current_quantity = float(position.get("quantity", 0.0)) if has_position else 0.0

        if side == "buy":
            order = self.exchange.create_market_buy_order(sym, qty)
            fill_px = float(order.get("price") or current_price)
            if has_position:
                self.positions[sym]["quantity"] = current_quantity + qty
                self.positions[sym]["entry_price"] = (
                    float(position["entry_price"]) * current_quantity + fill_px * qty
                ) / (current_quantity + qty)
                self.positions[sym]["timestamp"] = order.get("datetime")
            else:
                self.positions[sym] = {
                    "quantity": qty,
                    "entry_price": fill_px,
                    "timestamp": order.get("datetime"),
                }
            self.save_positions()
        elif side == "sell" and has_position and current_quantity >= qty - 1e-8:
            order = self.exchange.create_market_sell_order(sym, qty)
            self.positions[sym]["quantity"] = current_quantity - qty
            if self.positions[sym]["quantity"] <= 1e-12:
                del self.positions[sym]
            self.save_positions()

    def _execute_multi_trades(self, trades: Dict[str, Any], market_data: Dict[str, Any]) -> None:
        """Sells before buys so cash is freed (same ordering idea as the backtest engine)."""
        proposed: list[tuple[str, Dict[str, Any]]] = [
            (s, t)
            for s, t in trades.items()
            if isinstance(t, dict) and t.get("status") == "proposed"
        ]
        sells: list[tuple[str, Dict[str, Any]]] = []
        buys: list[tuple[str, Dict[str, Any]]] = []
        other: list[tuple[str, Dict[str, Any]]] = []
        for s, t in proposed:
            a = str(t.get("action") or "").lower()
            if a == "sell":
                sells.append((s, t))
            elif a == "buy":
                buys.append((s, t))
            else:
                other.append((s, t))

        for sym, tr in sells + buys + other:
            ohlcv = (market_data.get(sym) or {}).get("ohlcv") or []
            cp = float(ohlcv[-1][4]) if ohlcv else 0.0
            if cp <= 0:
                continue
            self._execute_one_market_order(sym, tr, cp)

    def analyze(
        self,
        ticker: str,
        market_data: Dict,
        pattern_analysis: Dict,
        sentiment_analysis: Dict,
        arb_analysis: Dict,
        quant_analysis: Dict,
        valuation: Dict,
        risk: Dict,
        liquidity: Dict,
        *,
        execute: bool = True,
        run_mode: str | None = None,
        external_position_qty: float | None = None,
        external_cash_usd: float | None = None,
        external_entry_avg_price: float | None = None,
        external_positions: Dict[str, float] | None = None,
        external_entry_avg_by_symbol: Dict[str, float] | None = None,
        strategy_context: Dict[str, Any] | None = None,
        trade_intent: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        try:
            market_data = market_data if isinstance(market_data, dict) else {}
            pattern_analysis = pattern_analysis if isinstance(pattern_analysis, dict) else {}
            sentiment_analysis = sentiment_analysis if isinstance(sentiment_analysis, dict) else {}
            arb_analysis = arb_analysis if isinstance(arb_analysis, dict) else {}
            quant_analysis = quant_analysis if isinstance(quant_analysis, dict) else {}
            valuation = valuation if isinstance(valuation, dict) else {}
            risk = risk if isinstance(risk, dict) else {}
            liquidity = liquidity if isinstance(liquidity, dict) else {}

            allocations: Dict[str, Any] = {}
            total_budget = float(self._trading.config.portfolio_budget_usd)
            # Backtest sizing should actually put capital to work. When the engine passes cash,
            # use it as the base budget and scale by leverage so 3x/5x/10x changes exposure.
            run_m = (run_mode or "").strip().lower()
            if run_m == "backtest" and external_cash_usd is not None:
                cash_f = float(external_cash_usd)
                lev = float(self._trading.config.max_leverage)
                total_budget = max(0.0, cash_f * lev)
            risk_analysis = risk.get("analysis") if isinstance(risk.get("analysis"), dict) else {}
            tickers = _valid_tickers(market_data)
            if not tickers:
                logger.warning("No valid market data for portfolio allocation")
                return {"status": "error", "message": "No valid market data"}

            total_position_size = sum(
                float(risk_analysis.get(t, {}).get("position_size", 0) or 0) for t in tickers
            )
            if total_position_size == 0:
                logger.warning("No position sizes available for allocation")
                return {"status": "error", "message": "No position sizes"}

            for t in tickers:
                position_size = float(risk_analysis.get(t, {}).get("position_size", 0) or 0)
                weight = position_size / total_position_size if total_position_size > 0 else 0
                amount = weight * total_budget
                allocations[t] = {
                    "weight": weight,
                    "amount": amount,
                    "stop_price": risk_analysis.get(t, {}).get("stop_price", 0),
                }

            trades: Dict[str, Any] = {}
            multi = _use_multi_asset_path(
                tickers, run_m=run_m, external_positions=external_positions
            )

            if run_m != "backtest":
                if multi:
                    bad = [s for s in tickers if s not in self.exchange.markets]
                    if bad:
                        msg = f"Tickers not on exchange: {bad}"
                        logger.error(msg)
                        return {
                            "status": "error",
                            "message": msg,
                            "trades": {s: {"status": "error", "message": msg} for s in bad},
                        }
                elif ticker not in self.exchange.markets:
                    logger.error(f"Ticker {ticker} not available on exchange")
                    trades[ticker] = {
                        "status": "error",
                        "message": f"Ticker {ticker} not available",
                    }
                    return {"status": "error", "trades": trades}

            if multi:
                pos_map, entry_map = self._multi_position_maps(
                    tickers,
                    run_m=run_m,
                    external_positions=external_positions,
                    external_entry_avg_by_symbol=external_entry_avg_by_symbol,
                )
                trades = self._build_multi_trades(
                    tickers,
                    market_data=market_data,
                    allocations=allocations,
                    quant_analysis=quant_analysis,
                    arb_analysis=arb_analysis,
                    sentiment_analysis=sentiment_analysis,
                    trade_intent=trade_intent,
                    run_m=run_m,
                    external_cash_usd=external_cash_usd,
                    pos_map=pos_map,
                    entry_map=entry_map,
                )
                if execute and run_m != "backtest":
                    self._execute_multi_trades(trades, market_data)
                return {
                    "status": "success",
                    "trades": trades,
                    "allocations": allocations,
                    "multi_asset": True,
                }

            sentiment_score = float(
                sentiment_analysis.get("sentiment_score") or sentiment_analysis.get("score") or 50.0
            )
            arb_signal = (
                (
                    arb_analysis.get("analysis")
                    if isinstance(arb_analysis.get("analysis"), dict)
                    else {}
                )
                .get(f"{ticker}-*", {})
                .get("signal", "hold")
            )
            qa = quant_analysis.get("analysis")
            qtick = qa.get(ticker, {}) if isinstance(qa, dict) else {}
            quant_signal = (
                qtick.get("macd_signal", "hold")
                if isinstance(qtick, dict)
                else quant_analysis.get("signal", "hold")
            )
            regime = qtick.get("ema_sma_regime") if isinstance(qtick, dict) else None

            ohlcv = market_data.get(ticker, {}).get("ohlcv", [])
            current_price = float(ohlcv[-1][4]) if ohlcv and len(ohlcv) > 0 else 0.0
            if current_price <= 0:
                logger.warning(f"Invalid current price for {ticker}")
                return {"status": "error", "message": "Invalid price"}

            position = self.positions.get(ticker)
            if run_m == "backtest":
                current_quantity = float(external_position_qty or 0.0)
                has_position = current_quantity > 0
            else:
                has_position = position is not None
                current_quantity = position.get("quantity", 0.0) if has_position else 0.0

            action = str(
                trade_intent.get("action") if isinstance(trade_intent, dict) else "HOLD"
            ).upper()
            confidence = trade_intent.get("confidence") if isinstance(trade_intent, dict) else None
            conf_f = float(confidence) if isinstance(confidence, (int, float)) else 0.0

            portfolio_alloc = allocations.get(ticker, {})
            target_amount = portfolio_alloc.get("amount", 0)
            target_quantity = target_amount / current_price if current_price > 0 else 0.0

            entry_px = 0.0
            if run_m == "backtest":
                entry_px = float(external_entry_avg_price or 0.0)
            elif has_position and isinstance(position, dict):
                try:
                    entry_px = float(position.get("entry_price") or 0.0)
                except (TypeError, ValueError):
                    entry_px = 0.0

            ctx = PortfolioDecisionContext(
                ticker=ticker,
                current_price=current_price,
                target_quantity=target_quantity,
                current_quantity=current_quantity,
                entry_avg_price=entry_px,
                run_mode=run_m,
                intent_action=action,
                intent_confidence=conf_f,
                sentiment_score=sentiment_score,
                quant_signal=str(quant_signal),
                arb_signal=str(arb_signal),
                ema_sma_regime=str(regime) if regime is not None else None,
                external_cash_usd=float(external_cash_usd)
                if external_cash_usd is not None
                else None,
            )
            trade_result = self._trading.decide(ctx)

            if execute and run_m != "backtest":
                self._execute_one_market_order(ticker, trade_result, current_price)

            return {
                "status": "success",
                "trades": {ticker: trade_result},
                "allocations": allocations,
            }

        except Exception as e:
            logger.error(f"Error in PortfolioManagementAgent.analyze: {str(e)}")
            return {"status": "error", "message": str(e)}
