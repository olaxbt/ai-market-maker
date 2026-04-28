# AI Market Maker - OpenClaw Usage Guide

## Quick Start

### Method 1: Install from GitHub
```bash
# From OpenClaw
claw install https://github.com/olaxbt/ai-market-maker

# Or clone and install locally
git clone https://github.com/olaxbt/ai-market-maker.git
cd ai-market-maker
claw skill install ./openclaw
```

### Method 2: Manual Execution
```bash
# Verify installation
./openclaw/scripts/verify_installation.sh

# Paper trading mode
python3 openclaw/scripts/claw_runner.py --paper --ticker BTC/USDT

# Backtesting mode
python3 openclaw/scripts/claw_runner.py --backtest --symbols BTC/USDT,ETH/USDT --steps 100
```

## Platform / Leadpage (Leaderboard + Providers)

This repo includes a lightweight platform surface:

- Providers (engines/traders) can publish results
- A leaderboard page at `/leadpage`
- Optional Postgres storage when `DATABASE_URL` is set

### Local Postgres (optional but recommended)

```bash
docker compose up -d
export DATABASE_URL="postgresql+psycopg://aimm:aimm@127.0.0.1:5432/aimm"
```

### Publish a provider result (signed)

```bash
export LEADPAGE_PROVIDER_KEYS="demoProvider:demoKey"
export LEADPAGE_REQUIRE_SIGNED=1

python3 scripts/publish_leadpage_result.py \
  --base-url http://127.0.0.1:8001 \
  --provider demoProvider \
  --run-id r1 \
  --total-return-pct 1.2 \
  --signed --key demoKey
```

### Publish a signal (strategy / ops / discussion)

Signals appear on the dashboard feed at `/feed` (and on each provider page).

```bash
curl -X POST "http://127.0.0.1:8001/signals/publish" \
  -H "Content-Type: application/json" \
  -H "x-leadpage-provider-key: demoKey" \
  -d '{
    "provider": "demoProvider",
    "kind": "strategy",
    "title": "Weekly bias: range fade",
    "body": "Plan: fade extremes; reduce size into events; tighten risk guard thresholds.",
    "ticker": "BTC/USDT",
    "meta": { "timeframe": "1h" }
  }'
```

## Operational Modes

### 1. Paper Trading Mode
```bash
# Basic usage
python3 openclaw/scripts/claw_runner.py --paper --ticker BTC/USDT

# Multiple symbol monitoring
python3 openclaw/scripts/claw_runner.py --paper --ticker "BTC/USDT,ETH/USDT,SOL/USDT"

# Custom interval (seconds)
export STRATEGY_INTERVAL_SEC=300
python3 openclaw/scripts/claw_runner.py --paper
```

### 2. 回測模式 (Backtesting)
```bash
# 快速回測
python3 openclaw/scripts/claw_runner.py --backtest --symbols BTC/USDT --steps 50

# 多幣種回測
python3 openclaw/scripts/claw_runner.py --backtest --symbols "BTC/USDT,ETH/USDT" --steps 100

# 完整歷史評估
python3 -m backtest.run_historical_eval --suite daily --max-windows 3
```

### 3. 驗證模式 (Verification)
```bash
# 完整驗證
python3 openclaw/scripts/claw_runner.py --verify

# 或使用 Shell 腳本
./openclaw/scripts/verify_installation.sh
```

## 🔧 配置說明

### 環境變數配置
```bash
# 複製範例配置
cp .env.example .env

# 編輯 .env 文件
nano .env
```

#### 關鍵配置項：
```env
# Nexus API (演示金鑰已包含)
NEXUS_API_KEY=4Qbp6biPAKPS1gOksAySOlqK
NEXUS_DISABLE=0

# Binance 測試網 (可選)
BINANCE_API_KEY=your_testnet_key
BINANCE_API_SECRET=your_testnet_secret

# OpenAI (可選，啟用 LLM 功能)
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o-mini

# 策略設定
AIMM_DESK_STRATEGY_PRESET=default
STRATEGY_INTERVAL_SEC=180
```

### 策略配置
配置文件位於 `config/` 目錄：
- `config/app.default.json` - 應用設定
- `config/policy.default.json` - 交易策略設定

## 🐛 常見問題解決

### 問題 1: TA-Lib 安裝失敗
```bash
# OpenClaw 環境推薦使用 Conda
conda install -y ta-lib -c conda-forge

# 或使用系統包管理器
sudo apt-get install -y ta-lib  # Ubuntu/Debian
brew install ta-lib            # macOS
```

### 問題 2: 模塊導入錯誤
```bash
# 安裝開發模式
pip install -e .

# 或手動添加路徑
export PYTHONPATH=/path/to/ai-market-maker/src:$PYTHONPATH
```

### 問題 3: Nexus API 限流
```
⚠️ 使用演示金鑰時可能遇到限流
解決方案：
1. 申請自己的 Nexus API 金鑰
2. 降低請求頻率
3. 啟用本地緩存
```

### 問題 4: 缺少依賴
```bash
# 安裝所有依賴
pip install -r requirements.txt

# 或使用 uv
uv sync --extra dev
```

## 🎯 韓國社區最佳實踐

### 1. 分享準備
```bash
# 1. 驗證安裝
./openclaw/scripts/verify_installation.sh

# 2. 運行快速測試
python3 openclaw/scripts/claw_runner.py --paper --ticker BTC/USDT

# 3. 截圖或錄製演示
# 4. 分享到韓國 Claw 社區
```

### 2. 社區標籤
在分享時使用以下標籤：
- `#OpenClaw`
- `#AgenticTrading` 
- `#KoreanClawCommunity`
- `#AIMarketMaker`
- `#CryptoHedgeFund`

### 3. 反饋收集模板
```
項目：AI Market Maker - OpenClaw 版本
測試環境：[你的環境]
測試結果：[成功/失敗]
遇到問題：[詳細描述]
建議改進：[你的建議]
```

## 📈 進階功能

### 1. 自定義代理配置
```python
# 創建 custom_agent.py
from src.agents.base_agent import BaseAgent

class CustomTradingAgent(BaseAgent):
    def process(self, context):
        # 自定義交易邏輯
        return {"signal": "BUY", "confidence": 0.8}
```

### 2. 數據源擴展
```python
# 添加新的數據源
from src.tools.data_fetcher import DataFetcher

class CustomDataFetcher(DataFetcher):
    async def fetch_custom_data(self, symbol):
        # 自定義數據獲取邏輯
        return {"price": 50000, "volume": 1000}
```

### 3. 風險規則自定義
編輯 `config/policy.default.json` 中的 `policy` 部分：
```json
{
  "policy": {
    "stop_loss_pct": 0.03,
    "take_profit_pct": 0.08,
    "max_leverage": 4,
    "min_confidence_directional": 0.45
  }
}
```

## 🤝 貢獻指南

### 1. 報告問題
- 使用 GitHub Issues
- 提供詳細的重現步驟
- 包含環境信息

### 2. 提交改進
```bash
# 1. Fork 倉庫
# 2. 創建功能分支
git checkout -b feature/openclaw-improvement

# 3. 提交更改
git commit -m "feat: improve OpenClaw integration"

# 4. 推送到分支
git push origin feature/openclaw-improvement

# 5. 創建 Pull Request
```

### 3. 測試要求
- 所有更改必須通過驗證腳本
- 新增功能需要文檔
- 保持向後兼容性

## Support

### Official Resources
- GitHub: https://github.com/olaxbt/ai-market-maker
- Documentation: https://github.com/olaxbt/ai-market-maker/docs
- Issue Tracker: https://github.com/olaxbt/ai-market-maker/issues

---

**Ready to start trading?**

```bash
# Final step: Start trading!
python3 openclaw/scripts/claw_runner.py --paper --ticker BTC/USDT
```