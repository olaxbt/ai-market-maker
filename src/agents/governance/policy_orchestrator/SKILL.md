# Skill: Policy Orchestrator

## Capabilities
- `evaluate(signal, user_config)` → route decision + policy check
- Direct query: "Is BTC allowed for this user?"
- Direct query: "What are the current policy rules?"

## Data Sources
- `config/policy_loader.py` — runtime policy definitions
- `config/policy_types.py` — policy schema

## Query Interface
```
/policy_orchestrator?ticker=BTC/USDT&action=check
```
Returns: allowed/blocked + route + reason + policy_id.

## Dependencies
- `policy_loader` for hot-reloadable rules
- No external API dependencies
