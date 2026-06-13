# Skill: Profile Agent

## Capabilities
- `process(questionnaire)` → weight deltas + narrative
- Direct query: "Generate a profile for a conservative swing trader"
- Direct query: "What weights would an aggressive scalper get?"

## Data Sources
- Built-in rule matrix (no external dependencies)
- Optional LLM client (Hermes/OpenAI)

## Query Interface
```
POST /profile-agent
{
  "risk_tolerance": "moderate",
  "time_horizon": "swing",
  "preferred_signals": "technical",
  "leverage_comfort": "1-3x",
  "assets": "majors_only"
}
```
Returns: profile JSON with deltas + effective weights + narrative.

## Dependencies
- `llm/openai_client.py` (optional, for LLM-enhanced mode)
- No external API calls in rule-based mode
