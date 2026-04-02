import json
import logging
import os
from typing import Any, Dict

import ccxt

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


class PortfolioManagementAgent:
    def __init__(self, exchange: str = "binance", testnet: bool = False):
        self.exchange = getattr(ccxt, exchange)(
            {
                "apiKey": os.getenv("BINANCE_API_KEY"),
                "secret": os.getenv("BINANCE_API_SECRET"),
                "enableRateLimit": True,
            }
        )
        if testnet:
            self.exchange.set_sandbox_mode(True)
        self.exchange.load_markets()
        self.positions_file = "positions.json"
        self.load_positions()

    def load_positions(self):
        """Load current positions from file."""
        try:
            if os.path.exists(self.positions_file):
                with open(self.positions_file, "r") as f:
                    # {ticker: {quantity, entry_price, timestamp}}
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

            # Step 1: Compute portfolio allocations
            allocations = {}
            total_budget = 5000  # Total USD budget
            risk_analysis = risk.get("analysis")
            risk_analysis = risk_analysis if isinstance(risk_analysis, dict) else {}
            tickers = [
                t for t in market_data if market_data[t].get("status") in ("success", "backtest")
            ]
            if not tickers:
                logger.warning("No valid market data for portfolio allocation")
                return {"status": "error", "message": "No valid market data"}

            # Allocate based on risk-adjusted position sizes
            total_position_size = sum(
                risk_analysis.get(t, {}).get("position_size", 0) for t in tickers
            )
            if total_position_size == 0:
                logger.warning("No position sizes available for allocation")
                return {"status": "error", "message": "No position sizes"}

            for t in tickers:
                position_size = risk_analysis.get(t, {}).get("position_size", 0)
                weight = position_size / total_position_size if total_position_size > 0 else 0
                amount = weight * total_budget
                allocations[t] = {
                    "weight": weight,
                    "amount": amount,  # USD amount to allocate
                    "stop_price": risk_analysis.get(t, {}).get("stop_price", 0),
                }

            # Step 2: Create proposal and (optionally) execute
            trades: Dict[str, Any] = {}
            if ticker not in self.exchange.markets:
                logger.error(f"Ticker {ticker} not available on exchange")
                trades[ticker] = {"status": "error", "message": f"Ticker {ticker} not available"}
            else:
                # Extract signals and portfolio allocations
                sentiment_score = float(
                    sentiment_analysis.get("sentiment_score")
                    or sentiment_analysis.get("score")
                    or 50.0
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
                intent = trade_intent if isinstance(trade_intent, dict) else {}
                action = str(intent.get("action") or "HOLD").upper()
                confidence = intent.get("confidence")
                conf_f = float(confidence) if isinstance(confidence, (int, float)) else 0.0
                portfolio_alloc = allocations.get(ticker, {})
                target_amount = portfolio_alloc.get("amount", 0)  # USD amount to allocate
                stop_price = portfolio_alloc.get("stop_price", 0)
                # Latest closing price
                current_price = market_data[ticker]["ohlcv"][-1][4]

                # Check current position (backtest uses engine-reported qty, not positions.json)
                position = self.positions.get(ticker, None)
                run_m = (run_mode or "").strip().lower()
                if run_m == "backtest":
                    current_quantity = float(
                        external_position_qty if external_position_qty is not None else 0.0
                    )
                    has_position = current_quantity > 0
                else:
                    has_position = position is not None
                    current_quantity = position["quantity"] if has_position else 0

                trade_result = {"status": "skipped", "message": "No trade signal"}

                # Calculate target quantity based on portfolio allocation
                target_quantity = target_amount / current_price if current_price > 0 else 0

                # Buy logic: Increase position to match target allocation
                if target_quantity > current_quantity:
                    if run_m == "backtest":
                        buy_signal = action == "BUY" and conf_f >= 0.55
                    else:
                        if action in ("BUY", "SELL"):
                            buy_signal = action == "BUY" and conf_f >= 0.55
                        else:
                            buy_signal = (sentiment_score > 75 and quant_signal == "buy") or (
                                arb_signal == "buy"
                            )

                    if buy_signal:
                        quantity_to_buy = target_quantity - current_quantity
                        if run_m == "backtest":
                            quantity_to_buy = min(quantity_to_buy, 0.05)
                            if external_cash_usd is not None and current_price > 0:
                                quantity_to_buy = min(
                                    quantity_to_buy,
                                    float(external_cash_usd) / float(current_price),
                                )
                        trade_result = {
                            "status": "proposed",
                            "action": "buy",
                            "quantity": quantity_to_buy,
                            "reason": {
                                "sentiment_score": sentiment_score,
                                "quant_signal": quant_signal,
                                "arb_signal": arb_signal,
                                "target_quantity": target_quantity,
                                "current_quantity": current_quantity,
                            },
                        }
                        if execute:
                            order = self.exchange.create_market_buy_order(ticker, quantity_to_buy)
                            if has_position:
                                # Update position
                                self.positions[ticker]["quantity"] += quantity_to_buy
                                self.positions[ticker]["entry_price"] = (
                                    position["entry_price"] * current_quantity
                                    + order["price"] * quantity_to_buy
                                ) / (current_quantity + quantity_to_buy)
                                self.positions[ticker]["timestamp"] = order["datetime"]
                            else:
                                self.positions[ticker] = {
                                    "quantity": quantity_to_buy,
                                    "entry_price": order["price"],
                                    "timestamp": order["datetime"],
                                }
                            self.save_positions()
                            logger.info(f"Placed buy order for {ticker}: {order}")
                            with open("trades.log", "a") as f:
                                f.write(
                                    f"{ticker},buy,{quantity_to_buy},{order['price']},{order['datetime']}\n"
                                )
                            trade_result = {
                                "status": "success",
                                "order": order,
                                "position": self.positions[ticker],
                                "profit_loss": 0.0,
                            }

                # Sell logic: Reduce position if below target or signals are negative
                elif has_position:
                    entry_price = position["entry_price"]
                    if run_m == "backtest":
                        should_sell = action == "SELL" and conf_f >= 0.55
                    else:
                        if action in ("BUY", "SELL"):
                            should_sell = action == "SELL" and conf_f >= 0.55
                        else:
                            should_sell = (
                                (target_quantity < current_quantity)
                                or (
                                    sentiment_score < 25
                                    or quant_signal == "sell"
                                    or arb_signal == "sell"
                                )
                                or (stop_price > 0 and current_price <= stop_price)
                            )
                    if should_sell:
                        quantity_to_sell = (
                            min(current_quantity - target_quantity, current_quantity)
                            if target_quantity < current_quantity
                            else current_quantity
                        )
                        if quantity_to_sell > 0:
                            trade_result = {
                                "status": "proposed",
                                "action": "sell",
                                "quantity": quantity_to_sell,
                                "reason": {
                                    "sentiment_score": sentiment_score,
                                    "quant_signal": quant_signal,
                                    "arb_signal": arb_signal,
                                    "stop_price": stop_price,
                                    "current_price": current_price,
                                    "entry_price": entry_price,
                                    "target_quantity": target_quantity,
                                    "current_quantity": current_quantity,
                                },
                            }
                            if execute:
                                order = self.exchange.create_market_sell_order(
                                    ticker, quantity_to_sell
                                )
                                profit_loss = (order["price"] - entry_price) * quantity_to_sell
                                remaining_quantity = current_quantity - quantity_to_sell
                                if remaining_quantity <= 0:
                                    del self.positions[ticker]
                                else:
                                    self.positions[ticker]["quantity"] = remaining_quantity
                                self.save_positions()
                                logger.info(
                                    f"Placed sell order for {ticker}: {order}, "
                                    f"Profit/Loss: {profit_loss}"
                                )
                                with open("trades.log", "a") as f:
                                    f.write(
                                        f"{ticker},sell,{quantity_to_sell},{order['price']},{order['datetime']},{profit_loss}\n"
                                    )
                                trade_result = {
                                    "status": "success",
                                    "order": order,
                                    "position": self.positions.get(ticker, None),
                                    "profit_loss": profit_loss,
                                }
                    else:
                        current_value = current_price * current_quantity
                        entry_value = entry_price * current_quantity
                        profit_loss = current_value - entry_value
                        trade_result = {
                            "status": "hold",
                            "message": "Holding position",
                            "position": position,
                            "profit_loss": profit_loss,
                        }

                trades[ticker] = trade_result

            # Step 3: Return allocations and trades (proposal if execute=False)
            result = {"status": "success", "allocations": allocations, "trades": trades}
            logger.info(f"Portfolio result: {result}")
            return result

        except Exception as e:
            logger.error(f"Portfolio analysis error: {str(e)}")
            return {"status": "error", "message": str(e)}
