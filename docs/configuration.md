## Configuration

Default settings live in versioned JSON files under the `config/` folder.

Use `.env` **only** for secrets, API endpoints, and run mode. Strategy and policy values should stay in git.

### Quick Start

```bash
uv run python -u src/main.py --ticker BTC/USDT