# Contributing

Thanks for helping improve this repo. Bug fixes, tests, and focused doc updates are welcome.

## Quick start

```bash
git clone https://github.com/olaxbt/ai-market-maker.git
cd ai-market-maker
uv sync
uv run pytest -q
```

Optional dev tooling:

```bash
uv sync --extra dev
uv run pre-commit install
uv run pre-commit run --all-files
```

## Guidelines

- Match existing style in `src/` (types, logging, layout).
- Keep PRs small and on-topic; avoid drive-by refactors.
- Add or update tests when behavior changes. Use `@pytest.mark.slow` for heavy or network tests.
- If you change **policy fields**, **env knobs**, or **run modes**, update the relevant doc: `docs/configuration.md`, `docs/policy-schema.md`, or `docs/run-modes.md`, and `.env.example` when users need new variables.

## Pull requests

Use the [PR template](.github/pull_request_template.md). Describe what changed, why, and how to verify. Avoid unsubstantiated performance or PnL claims.

## Security

Do not commit secrets. Use `.env` locally; only placeholders go in `.env.example`.

## Questions

Open an issue for bugs or design questions before large features.
