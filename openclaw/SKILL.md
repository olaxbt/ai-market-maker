# AI Market Maker Skill - OpenClaw Edition 🦀

## Purpose

This skill provides a complete, **OpenClaw-ready** agentic trading system for crypto hedge funds. Built specifically for the **Korean Claw Community**, it includes multi-agent LangGraph workflows, hard Risk Guard veto, and full OpenClaw integration.

## 🚀 Quick Start for OpenClaw Users

### One-Click Installation
```bash
# From OpenClaw terminal
claw install https://github.com/OlaXBT-DavisNexus/ai-market-maker

# Or clone and install locally
git clone https://github.com/OlaXBT-DavisNexus/ai-market-maker.git
cd ai-market-maker
claw skill install ./openclaw
```

### Verify Installation
```bash
# Run verification script
./openclaw/scripts/verify_installation.sh

# Or use Python runner
python3 openclaw/scripts/claw_runner.py --verify
```

### Start Trading
```bash
# Paper trading mode
python3 openclaw/scripts/claw_runner.py --paper --ticker BTC/USDT

# Backtesting mode
python3 openclaw/scripts/claw_runner.py --backtest --symbols BTC/USDT --steps 100
```

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

## 🐛 Common Issues & Fixes (OpenClaw Edition)

### 1. TA-Lib Installation
**Problem:** `ModuleNotFoundError: No module named 'talib'`
**Solution:**
```bash
# OpenClaw environments often lack sudo - use Conda
conda install -y ta-lib -c conda-forge

# Or install from source (no sudo required)
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

# Or manually add to Python path
export PYTHONPATH=/path/to/ai-market-maker/src:$PYTHONPATH
```

### 3. Nexus API Rate Limits
**Problem:** `429 Too Many Requests`
**Solution:**
- Demo key included (rate-limited)
- Set your own Nexus API key in `.env` for production
- Implement request caching in your strategy

### 4. OpenClaw Environment Detection
**Problem:** Environment variables not set correctly
**Solution:**
```bash
# The claw_runner.py automatically detects and configures:
# - Python path
# - Nexus API keys
# - Strategy settings
# - Error handling

# Manual override if needed
export NEXUS_API_KEY=your_key_here
export AIMM_DESK_STRATEGY_PRESET=trend_guard
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

## 🎯 Korean Claw Community Guidelines

### Best Practices for Sharing
1. **Always verify installation** before sharing
2. **Include environment details** in bug reports
3. **Use community tags**: `#OpenClaw #AgenticTrading #KoreanClawCommunity`
4. **Share success stories** and learning experiences

### Community Support Channels
- GitHub Issues: https://github.com/OlaXBT-DavisNexus/ai-market-maker/issues
- Korean Claw Telegram/Discord groups
- ClawHub discussion forums

## 🔑 Key Files for OpenClaw Integration

| Area | Location | Purpose |
|------|----------|---------|
| OpenClaw Runner | `openclaw/scripts/claw_runner.py` | Main entry point for Claw |
| Installation Verifier | `openclaw/scripts/verify_installation.sh` | Dependency checker |
| Skill Manifest | `openclaw/manifest.json` | OpenClaw skill definition |
| Usage Examples | `openclaw/examples/claw_usage.md` | Korean/English guides |
| Main Workflow | `src/main.py` | Core trading logic |
| Agent System | `src/agents/` | 7 trading desks |
| Web Dashboard | `web/` | Next.js monitoring UI |

## 📈 Performance Tips for OpenClaw

1. **Enable Caching**: Reduce API calls with local OHLCV cache
2. **Adjust Intervals**: Increase `STRATEGY_INTERVAL_SEC` for lower resource usage
3. **Use Paper Mode**: Test strategies without real funds
4. **Monitor Resources**: Check memory/CPU usage in resource-constrained environments

## 🤝 Contributing to OpenClaw Edition

We welcome contributions from the Korean Claw Community!

### Priority Areas:
1. **Better error messages** in Korean/English
2. **Simplified installation** for new users
3. **Performance optimizations** for resource-limited environments
4. **Community documentation** and tutorials

### How to Contribute:
```bash
# 1. Fork the repository
# 2. Create a feature branch
git checkout -b feature/openclaw-improvement

# 3. Make your changes
# 4. Test with verification script
./openclaw/scripts/verify_installation.sh

# 5. Submit Pull Request
```

## 📞 Support & Community

- **GitHub**: https://github.com/OlaXBT-DavisNexus/ai-market-maker
- **Email**: olaxbt-davis@olaxbt.xyz
- **Korean Community**: Telegram/Discord groups
- **Documentation**: `openclaw/examples/claw_usage.md`

---

**Korean Claw Community Approved** 🎯 - This skill follows community best practices for OpenClaw integration and agentic trading systems.

**Version**: 1.0.0 (OpenClaw Enhanced)
**Last Updated**: 2026-04-17
**Community Tag**: `#KoreanClawCommunity #OpenClawReady #AgenticTrading`
