# LangGraph Workflow

The core orchestration is a **LangGraph** state machine that mirrors a real hedge-fund trading desk.

## Graph State
- `messages`: list of agent outputs
- `current_desk`: current active node
- `portfolio_state`
- `risk_guard_approval`: boolean + veto_reason
- `trade_proposal`

## Nodes (Desks)
1. Market Scan
2. Technical Analysis
3. Statistical Alpha
4. Sentiment & Narrative
5. Alpha Generation (synthesis)
6. Portfolio Management
7. Risk Guard (final veto)
8. Execution (Binance Testnet)

## Edges & Routing
- Conditional routing based on Risk Guard veto
- All paths converge on Risk Guard before execution
- Full traceability via `NexusPayload`

See `src/agents/` for the standardized `base_agent.py` interface and `src/api/` for the FastAPI + WebSocket exposure.
