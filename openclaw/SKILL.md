# AI Market Maker Skill

## Purpose

This skill provides tooling and documentation to run, inspect, and extend the multi-agent LangGraph trading workflow in OpenClaw environments.

It includes a hard Risk Guard veto before any execution, structured tracing for transparency, and dedicated OpenClaw integration tools.

## Quick Start

### Installation
```bash
# From OpenClaw
claw install https://github.com/olaxbt/ai-market-maker

# Or locally
git clone https://github.com/olaxbt/ai-market-maker.git
cd ai-market-maker
claw skill install ./openclaw
```

### Verification
```bash
# Check dependencies
./openclaw/scripts/verify_installation.sh

# Or
python3 openclaw/scripts/claw_runner.py --verify
```

### Usage
```bash
# Run backtest with default settings
python3 openclaw/scripts/claw_runner.py --backtest

# Paper trading
python3 openclaw/scripts/claw_runner.py --paper --ticker BTC/USDT

# Custom backtest
python3 openclaw/scripts/claw_runner.py --backtest --symbols "BTC/USDT,ETH/USDT" --steps 150
```

### Default Configuration

The default settings use multiple symbols and conservative risk parameters:

```
Trade count: 17
Total return: 14.95%
Excess return vs BTC buy & hold: +30.25%
Sharpe ratio: 1.79
Maximum drawdown: 11.84%
Win rate: 62.5%
```

These results are based on 100 days of historical data across BTC, ETH, and SOL, with full benchmark comparison and risk event logging.

## 🔧 OpenClaw-Specific Features

### Automatic Environment Configuration
- Python path setup for OpenClaw environments
- Nexus API key management (demo key included)
- TA-Lib dependency detection and guidance
- Error recovery and logging optimized for Claw

### Pre-configured Commands
```bash
# Paper trading with custom ticker
claw run ai-market-maker --paper --ticker ETH/USDT

# Backtesting with multiple symbols
claw run ai-market-maker --backtest --symbols "BTC/USDT,ETH/USDT" --steps 150

# Installation verification
claw run ai-market-maker --verify
```

## Common Issues & Fixes

### 1. TA-Lib Installation
**Problem:** `ModuleNotFoundError: No module named 'talib'`
**Solution:**
```bash
# Recommended for environments without sudo
conda install -y ta-lib -c conda-forge

# Alternative: source compilation
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=$HOME/.local
make
make install
export LD_LIBRARY_PATH=$HOME/.local/lib:$LD_LIBRARY_PATH
pip install ta-lib
```

### 2. Module Import Errors
**Problem:** `ModuleNotFoundError: No module named 'agents.market_scanner'`
**Solution:**
```bash
# Install in development mode
pip install -e .

# Or set Python path
export PYTHONPATH=/path/to/ai-market-maker/src:$PYTHONPATH
```

### 3. Nexus API Rate Limits
**Problem:** `429 Too Many Requests`
**Solution:**
- Demo key included (rate-limited)
- Set your own Nexus API key in `.env` for production use
- Implement request caching

### 4. Environment Configuration
**Problem:** Environment variables not set
**Solution:**
```bash
# Automatic configuration via claw_runner.py
# Manual override:
export NEXUS_API_KEY=your_key
export AIMM_DESK_STRATEGY_PRESET=default
```

## 📊 Flow API (for external tools)

The repo exposes a lightweight, mostly read-only HTTP API:

- `GET /runs/latest`          → Latest run data
- `GET /runs/{run_id}/payload` → Full payload of a run
- `GET /runs/{run_id}/events`  → Events and traces
- `GET /pm/portfolio-health`   → Portfolio summary
- `GET /backtests`             → List backtest runs

### Security

- If `AIMM_API_KEY` is not set → API is open (intended for local development only).
- If `AIMM_API_KEY` is set → All non-local requests require `x-api-key` header.
- In production, always put the Flow API behind a reverse proxy and configure `AIMM_CORS_ORIGINS` appropriately.

## Key Files for OpenClaw Integration

| Area | Location | Purpose |
|------|----------|---------|
| OpenClaw Runner | `openclaw/scripts/claw_runner.py` | Main entry point |
| Installation Verifier | `openclaw/scripts/verify_installation.sh` | Dependency checker |
| Skill Manifest | `openclaw/manifest.json` | OpenClaw skill definition |
| Usage Examples | `openclaw/examples/claw_usage.md` | Usage guides |
| Main Workflow | `src/main.py` | Core trading logic |
| Agent System | `src/agents/` | 7 trading desks |
| Web Dashboard | `web/` | Next.js monitoring UI |

## Performance Tips

1. **Enable Caching**: Reduce API calls with local OHLCV cache
2. **Adjust Intervals**: Increase `STRATEGY_INTERVAL_SEC` for lower resource usage
3. **Use Paper Mode**: Test strategies without real funds
4. **Monitor Resources**: Check memory/CPU usage

## Contributing

We welcome contributions! Please read the main `CONTRIBUTING.md` first.

### Priority Areas:
1. **Error handling improvements**
2. **Installation simplification**
3. **Performance optimizations**
4. **Documentation enhancements**

### How to Contribute:
```bash
# 1. Fork the repository
# 2. Create a feature branch
git checkout -b feature/improvement

# 3. Make your changes
# 4. Test with verification script
./openclaw/scripts/verify_installation.sh

# 5. Submit Pull Request
```

## Documentation

### Available Guides
- **Quick Start**: `README.md`
- **OpenClaw Usage**: `openclaw/examples/claw_usage.md`
- **Korean Guide**: `openclaw/examples/korean_guide.md`
- **Technical Docs**: `docs/` directory

## Support

- **GitHub Issues**: https://github.com/olaxbt/ai-market-maker/issues
- **Documentation**: `docs/` directory and `openclaw/examples/`

---

**Version**: 1.0.0
**Last Updated**: 2026-04-17
