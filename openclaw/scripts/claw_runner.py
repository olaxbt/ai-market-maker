#!/usr/bin/env python3
"""
OpenClaw-specific runner for AI Market Maker
Handles environment setup, path configuration, and error recovery
"""

import argparse
import os
import sys
from pathlib import Path


def setup_openclaw_environment():
    """Configure environment for OpenClaw execution"""
    # Add project root to Python path
    project_root = Path(__file__).parent.parent.parent
    src_path = project_root / "src"

    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    # Add project root for config access
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Set up environment variables
    os.environ.setdefault("AIMM_DESK_STRATEGY_PRESET", "default")
    os.environ.setdefault("STRATEGY_INTERVAL_SEC", "180")

    # Check for .env file
    env_file = project_root / ".env"
    if not env_file.exists():
        print("📝 Creating .env file from example...")
        example_env = project_root / ".env.example"
        if example_env.exists():
            import shutil

            shutil.copy(example_env, env_file)
            print("✅ Created .env from .env.example")
        else:
            print("⚠️  No .env.example found, creating minimal .env")
            with open(env_file, "w") as f:
                f.write("# AI Market Maker Environment\n")
                f.write("NEXUS_API_KEY=4Qbp6biPAKPS1gOksAySOlqK\n")
                f.write("NEXUS_DISABLE=0\n")

    # Load environment variables
    from dotenv import load_dotenv

    load_dotenv(env_file)

    return True


def run_paper_trading(ticker="BTC/USDT"):
    """Run paper trading mode"""
    print(f"📊 Starting paper trading for {ticker}")
    try:
        # Import after path setup
        from src.main import main as market_maker_main

        # Set command line arguments
        sys.argv = ["main.py", "--mode", "paper", "--ticker", ticker]

        return market_maker_main()
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Try: pip install -e . or check Python path")
        return 1
    except Exception as e:
        print(f"❌ Runtime error: {e}")
        import traceback

        traceback.print_exc()
        return 1


def run_backtest(symbols="BTC/USDT,ETH/USDT,SOL/USDT", steps=100):
    """Run backtest"""
    print(f"📈 Running backtest for {symbols} ({steps} steps)")
    try:
        from src.backtest.run_demo import main as backtest_main

        sys.argv = ["run_demo.py", "--symbols", symbols, "--steps", str(steps), "--online", "--exchange", "binance", "--timeframe", "1d", "--initial-cash", "10000"]
        
        # Add --ticker-only if only one symbol
        if len(symbols.split(',')) == 1:
            sys.argv.append("--ticker-only")

        return backtest_main()
    except Exception as e:
        print(f"❌ Backtest error: {e}")
        import traceback

        traceback.print_exc()
        return 1


def verify_installation():
    """Verify all dependencies are installed"""
    print("🔍 Verifying installation...")

    checks = []

    # Check Python version
    if sys.version_info >= (3, 11):
        checks.append(("✅", "Python 3.11+"))
    else:
        checks.append(
            ("❌", f"Python {sys.version_info.major}.{sys.version_info.minor} (3.11+ required)")
        )

    # Check TA-Lib
    try:
        import talib

        talib_version = talib.__version__
        checks.append(("✅", f"TA-Lib ({talib_version})"))
    except ImportError:
        checks.append(("❌", "TA-Lib (required for technical analysis)"))

    # Check core dependencies
    dependencies = [
        ("langgraph", "LangGraph"),
        ("ccxt", "CCXT"),
        ("pandas", "Pandas"),
        ("numpy", "NumPy"),
        ("openai", "OpenAI (optional)"),
    ]

    for module, name in dependencies:
        try:
            __import__(module)
            checks.append(("✅", name))
        except ImportError:
            if module == "openai":
                checks.append(("⚠️", f"{name} (optional for LLM features)"))
            else:
                checks.append(("❌", name))

    # Check project structure
    project_root = Path(__file__).parent.parent.parent
    required_files = [
        ("src/main.py", "Main entry point"),
        ("config/app.default.json", "App config"),
        ("config/policy.default.json", "Policy config"),
        ("openclaw/SKILL.md", "OpenClaw skill doc"),
    ]

    for file_path, description in required_files:
        if (project_root / file_path).exists():
            checks.append(("✅", description))
        else:
            checks.append(("❌", f"{description} (missing)"))

    # Print results
    print("\n📊 Verification Results:")
    for status, message in checks:
        print(f"  {status} {message}")

    # Summary
    success = sum(1 for status, _ in checks if status == "✅")
    total = len(checks)

    print(f"\n🎯 Score: {success}/{total} checks passed")

    if success == total:
        print("🚀 All checks passed! Ready to run.")
        return 0
    elif success >= total * 0.8:
        print("⚠️  Most checks passed. Some features may be limited.")
        return 0
    else:
        print("❌ Multiple issues found. Please fix before running.")
        return 1


def main():
    """Main entry point for OpenClaw"""
    parser = argparse.ArgumentParser(description="AI Market Maker - OpenClaw Edition")
    parser.add_argument("--paper", action="store_true", help="Run paper trading mode")
    parser.add_argument("--ticker", default="BTC/USDT", help="Ticker symbol (default: BTC/USDT)")
    parser.add_argument("--backtest", action="store_true", help="Run backtest mode")
    parser.add_argument(
        "--symbols", default="BTC/USDT,ETH/USDT,SOL/USDT", help="Symbols for backtest (default: BTC/USDT,ETH/USDT,SOL/USDT)"
    )
    parser.add_argument("--steps", type=int, default=100, help="Backtest steps (default: 100)")
    parser.add_argument("--verify", action="store_true", help="Verify installation")
    parser.add_argument("--version", action="store_true", help="Show version info")

    args = parser.parse_args()

    print("🦀 AI Market Maker - OpenClaw Edition")
    print("=" * 50)

    if args.version:
        print("Version: 1.0.0")
        print("Repository: https://github.com/olaxbt/ai-market-maker")
        return 0

    # Always setup environment
    if not setup_openclaw_environment():
        print("❌ Environment setup failed")
        return 1

    if args.verify:
        return verify_installation()
    elif args.backtest:
        return run_backtest(args.symbols, args.steps)
    elif args.paper:
        return run_paper_trading(args.ticker)
    else:
        # Default: verify and run paper trading
        print("No mode specified. Running verification and paper trading...\n")
        verify_result = verify_installation()
        if verify_result == 0:
            print("\n" + "=" * 50)
            return run_paper_trading(args.ticker)
        else:
            return verify_result


if __name__ == "__main__":
    sys.exit(main())
