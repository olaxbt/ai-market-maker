# LangGraph workflow notes

The trading pipeline is a **serial** LangGraph over [`HedgeFundState`](../src/schemas/state.py) (`src/main.py`, `build_workflow()`).

## State shape

- **Tier 3 fields** (`is_vetoed`, `veto_reason`, `risk_report`, `execution_result`, …) are first-class keys on `HedgeFundState`.
- **Pipeline workspace** (`ticker`, `market_data`, `proposal`, `risk_guard`, …) lives on the same dict as `NotRequired` keys until Tier 1/2 refactors fold them into `market_context` / `proposed_signal`.

## Node IDs vs state keys

LangGraph does **not** allow a **node name** to equal a **state key**. Where names would collide (e.g. `market_scan`, `valuation`, `risk`, `liquidity`, `risk_guard`), graph nodes use a `desk_*` prefix (e.g. `desk_market_scan`, `desk_risk_guard`).

## Partial updates

Fields annotated with `Annotated[..., operator.add]` (`market_context`, `debate_transcript`, `reasoning_logs`) must receive **append-only** fragments. Nodes therefore return **partial** updates (only keys they change), not `{**state, ...}` spreads that copy reducer lists.

## Risk gate

Routing after `desk_risk_guard` is implemented in [`src/workflow/routing.py`](../src/workflow/routing.py): veto → graph `END`; approve → `portfolio_execute`.

Flow telemetry: [`FlowEventRepo`](../src/flow_log.py) receives events from risk and execution nodes; extend to remaining desks as needed.
