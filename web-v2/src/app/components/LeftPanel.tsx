import { useState } from "react";
import { Activity, Trophy, LineChart, ChevronLeft, ChevronRight } from "lucide-react";

interface Trader {
  rank: number;
  name: string;
  pnl: number;
  winRate: number;
  trades: number;
}

interface BacktestResult {
  strategy: string;
  period: string;
  returns: number;
  sharpe: number;
  maxDrawdown: number;
}

interface LeftPanelProps {
  isCollapsed: boolean;
  onToggle: () => void;
}

export default function LeftPanel({ isCollapsed, onToggle }: LeftPanelProps) {
  const [activeTab, setActiveTab] = useState<"nexus" | "leaderboard" | "backtest">("nexus");

  const traders: Trader[] = [
    { rank: 1, name: "QuantMaster", pnl: 45320, winRate: 68.5, trades: 1247 },
    { rank: 2, name: "AlphaSeeker", pnl: 38940, winRate: 65.2, trades: 892 },
    { rank: 3, name: "MarketMaker", pnl: 32150, winRate: 71.3, trades: 1089 },
    { rank: 4, name: "FlowTrader", pnl: 28700, winRate: 63.8, trades: 756 },
    { rank: 5, name: "ArbitrageBot", pnl: 24500, winRate: 69.1, trades: 1523 }
  ];

  const backtests: BacktestResult[] = [
    { strategy: "Mean Reversion", period: "2024-Q1", returns: 23.5, sharpe: 1.8, maxDrawdown: -8.2 },
    { strategy: "Momentum", period: "2024-Q1", returns: 18.3, sharpe: 1.5, maxDrawdown: -12.1 },
    { strategy: "Market Making", period: "2024-Q1", returns: 31.2, sharpe: 2.1, maxDrawdown: -6.5 }
  ];

  if (isCollapsed) {
    return (
      <div className="w-12 bg-sidebar border-r border-sidebar-border flex flex-col items-center py-4 gap-4">
        <button
          onClick={onToggle}
          className="p-2 rounded-lg hover:bg-sidebar-accent transition-colors"
        >
          <ChevronRight className="w-4 h-4 text-sidebar-foreground" />
        </button>
        <button className="p-2 rounded-lg hover:bg-sidebar-accent transition-colors">
          <Activity className="w-4 h-4 text-sidebar-foreground" />
        </button>
        <button className="p-2 rounded-lg hover:bg-sidebar-accent transition-colors">
          <Trophy className="w-4 h-4 text-sidebar-foreground" />
        </button>
        <button className="p-2 rounded-lg hover:bg-sidebar-accent transition-colors">
          <LineChart className="w-4 h-4 text-sidebar-foreground" />
        </button>
      </div>
    );
  }

  return (
    <div className="w-80 bg-sidebar border-r border-sidebar-border flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-sidebar-border flex items-center justify-between">
        <h2 className="text-sidebar-foreground">Trading Hub</h2>
        <button
          onClick={onToggle}
          className="p-2 rounded-lg hover:bg-sidebar-accent transition-colors"
        >
          <ChevronLeft className="w-4 h-4 text-sidebar-foreground" />
        </button>
      </div>

      {/* Tabs */}
      <div className="border-b border-sidebar-border">
        <div className="flex">
          <button
            onClick={() => setActiveTab("nexus")}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 transition-colors ${
              activeTab === "nexus"
                ? "border-b-2 border-sidebar-primary text-sidebar-primary"
                : "text-sidebar-foreground hover:bg-sidebar-accent"
            }`}
          >
            <Activity className="w-4 h-4" />
            <span className="text-sm">Nexus</span>
          </button>
          <button
            onClick={() => setActiveTab("leaderboard")}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 transition-colors ${
              activeTab === "leaderboard"
                ? "border-b-2 border-sidebar-primary text-sidebar-primary"
                : "text-sidebar-foreground hover:bg-sidebar-accent"
            }`}
          >
            <Trophy className="w-4 h-4" />
            <span className="text-sm">Leaders</span>
          </button>
          <button
            onClick={() => setActiveTab("backtest")}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 transition-colors ${
              activeTab === "backtest"
                ? "border-b-2 border-sidebar-primary text-sidebar-primary"
                : "text-sidebar-foreground hover:bg-sidebar-accent"
            }`}
          >
            <LineChart className="w-4 h-4" />
            <span className="text-sm">Backtest</span>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === "nexus" && (
          <div className="space-y-4">
            <div className="bg-sidebar-accent rounded-lg p-4">
              <h3 className="mb-3 text-sidebar-foreground">System Status</h3>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-sidebar-foreground">Market Connection</span>
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                    <span className="text-sm text-green-500">Active</span>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-sidebar-foreground">Trading Engine</span>
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                    <span className="text-sm text-green-500">Running</span>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-sidebar-foreground">Risk Monitor</span>
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                    <span className="text-sm text-green-500">Normal</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-sidebar-accent rounded-lg p-4">
              <h3 className="mb-3 text-sidebar-foreground">Active Strategies</h3>
              <div className="space-y-3">
                <div className="p-3 bg-sidebar rounded-lg">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-sidebar-foreground">Market Making</span>
                    <span className="text-xs text-green-500">+2.3%</span>
                  </div>
                  <div className="text-xs text-muted-foreground">15 active positions</div>
                </div>
                <div className="p-3 bg-sidebar rounded-lg">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-sidebar-foreground">Arbitrage</span>
                    <span className="text-xs text-green-500">+1.8%</span>
                  </div>
                  <div className="text-xs text-muted-foreground">8 active positions</div>
                </div>
              </div>
            </div>

            <div className="bg-sidebar-accent rounded-lg p-4">
              <h3 className="mb-3 text-sidebar-foreground">Today's Performance</h3>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="text-xs text-muted-foreground">Total PnL</div>
                  <div className="text-green-500">+$3,247</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Win Rate</div>
                  <div className="text-sidebar-foreground">68.5%</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Trades</div>
                  <div className="text-sidebar-foreground">142</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Volume</div>
                  <div className="text-sidebar-foreground">$1.2M</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "leaderboard" && (
          <div className="space-y-3">
            <div className="mb-4">
              <h3 className="text-sidebar-foreground mb-1">Top Traders</h3>
              <p className="text-xs text-muted-foreground">Last 30 days</p>
            </div>
            {traders.map((trader) => (
              <div
                key={trader.rank}
                className="bg-sidebar-accent rounded-lg p-4 hover:bg-sidebar-accent/80 transition-colors"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <div className={`
                      w-8 h-8 rounded-full flex items-center justify-center
                      ${trader.rank === 1 ? 'bg-yellow-500/20 text-yellow-500' :
                        trader.rank === 2 ? 'bg-gray-400/20 text-gray-400' :
                        trader.rank === 3 ? 'bg-orange-500/20 text-orange-500' :
                        'bg-sidebar text-sidebar-foreground'}
                    `}>
                      #{trader.rank}
                    </div>
                    <div>
                      <div className="text-sidebar-foreground">{trader.name}</div>
                      <div className="text-xs text-muted-foreground">{trader.trades} trades</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-green-500">+${trader.pnl.toLocaleString()}</div>
                    <div className="text-xs text-muted-foreground">{trader.winRate}% win</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === "backtest" && (
          <div className="space-y-4">
            <div className="mb-4">
              <h3 className="text-sidebar-foreground mb-1">Backtest Results</h3>
              <p className="text-xs text-muted-foreground">Historical performance analysis</p>
            </div>
            {backtests.map((test, idx) => (
              <div key={idx} className="bg-sidebar-accent rounded-lg p-4">
                <h4 className="text-sidebar-foreground mb-3">{test.strategy}</h4>
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Period</span>
                    <span className="text-sidebar-foreground">{test.period}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Returns</span>
                    <span className="text-green-500">+{test.returns}%</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Sharpe Ratio</span>
                    <span className="text-sidebar-foreground">{test.sharpe}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Max Drawdown</span>
                    <span className="text-red-500">{test.maxDrawdown}%</span>
                  </div>
                </div>
                <button className="w-full mt-3 px-3 py-2 bg-sidebar-primary text-sidebar-primary-foreground rounded-lg text-sm hover:opacity-90 transition-opacity">
                  View Details
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
