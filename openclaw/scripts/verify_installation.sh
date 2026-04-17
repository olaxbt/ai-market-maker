#!/bin/bash
# OpenClaw installation verification script for AI Market Maker
# Korean Claw Community Approved 🎯

set -e

echo "🔍 AI Market Maker - OpenClaw Installation Verification"
echo "="======================================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅${NC} $1"
        return 0
    else
        echo -e "${RED}❌${NC} $1"
        return 1
    fi
}

warn() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

# Get project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "Project root: $PROJECT_ROOT"
echo ""

# 1. Python version check
echo "1. Checking Python environment..."
python3 --version | grep -q "3.1[1-9]" 
check "Python 3.11+"

# 2. TA-Lib check
echo "2. Checking TA-Lib..."
python3 -c "import talib; print('TA-Lib version:', talib.__version__)" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ TA-Lib installed${NC}"
else
    echo -e "${RED}❌ TA-Lib not installed${NC}"
    echo "   Install with: conda install -y ta-lib -c conda-forge"
    echo "   Or see README.md for other options"
fi

# 3. Core dependencies
echo "3. Checking core dependencies..."
for pkg in langgraph ccxt pandas numpy; do
    python3 -c "import $pkg; print('$pkg:', $pkg.__version__)" 2>/dev/null
    check "$pkg"
done

# 4. Optional dependencies
echo "4. Checking optional dependencies..."
python3 -c "import openai" 2>/dev/null && echo -e "${GREEN}✅ OpenAI (LLM support)${NC}" || warn "OpenAI not installed (optional for LLM)"

# 5. Project structure
echo "5. Checking project structure..."
[ -f "src/main.py" ] && check "Main entry point" || echo -e "${RED}❌ Main entry point missing${NC}"
[ -f "config/app.default.json" ] && check "App config" || echo -e "${RED}❌ App config missing${NC}"
[ -f "config/policy.default.json" ] && check "Policy config" || echo -e "${RED}❌ Policy config missing${NC}"
[ -f "openclaw/SKILL.md" ] && check "OpenClaw skill doc" || echo -e "${RED}❌ OpenClaw skill doc missing${NC}"
[ -f "openclaw/manifest.json" ] && check "OpenClaw manifest" || echo -e "${RED}❌ OpenClaw manifest missing${NC}"
[ -f "openclaw/scripts/claw_runner.py" ] && check "OpenClaw runner" || echo -e "${RED}❌ OpenClaw runner missing${NC}"

# 6. Environment file
echo "6. Checking environment configuration..."
if [ -f ".env" ]; then
    echo -e "${GREEN}✅ .env file found${NC}"
    if grep -q "NEXUS_API_KEY" .env; then
        echo -e "${GREEN}✅ Nexus API key configured${NC}"
    else
        warn "Nexus API key not found in .env"
    fi
else
    if [ -f ".env.example" ]; then
        warn ".env file not found, but .env.example exists"
        echo "   Copy: cp .env.example .env"
    else
        echo -e "${RED}❌ No .env or .env.example found${NC}"
    fi
fi

# 7. OpenClaw runner test
echo "7. Testing OpenClaw runner..."
python3 openclaw/scripts/claw_runner.py --verify 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ OpenClaw runner working${NC}"
else
    echo -e "${RED}❌ OpenClaw runner failed${NC}"
fi

echo ""
echo "="======================================================="
echo "🎯 Verification complete!"
echo ""
echo "Next steps:"
echo "1. Run paper trading: python3 openclaw/scripts/claw_runner.py --paper"
echo "2. Run backtest: python3 openclaw/scripts/claw_runner.py --backtest"
echo "3. For OpenClaw: claw skill install ./openclaw"
echo ""
echo "Korean Claw Community 🦀 - Happy trading!"