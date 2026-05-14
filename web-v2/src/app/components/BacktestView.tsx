import React, { useState } from "react";
import { Play, Download, Calendar, TrendingUp, Settings2, ChevronDown } from "lucide-react";
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

export default function BacktestView() {
  const [showConfig, setShowConfig] = useState(true);
  const [configData, setConfigData] = useState({
    strategy: "mean-reversion",
    symbol: "BTC/USD",
    timeframe: "1h",
    startDate: "2024-01-01",
    endDate: "2024-12-31",
    initialCapital: 100000,
    positionSize: 10,
    stopLoss: 2,
    takeProfit: 4
  });
  const equityCurveData = [
    { date: "Jan", equity: 10000, benchmark: 10000 },
    { date: "Feb", equity: 10850, benchmark: 10200 },
    { date: "Mar", equity: 11200, benchmark: 10350 },
    { date: "Apr", equity: 10900, benchmark: 10280 },
    { date: "May", equity: 12100, benchmark: 10500 },
    { date: "Jun", equity: 13200, benchmark: 10700 },
    { date: "Jul", equity: 12800, benchmark: 10650 },
    { date: "Aug", equity: 14200, benchmark: 10900 },
    { date: "Sep", equity: 15100, benchmark: 11100 },
    { date: "Oct", equity: 14800, benchmark: 11000 },
    { date: "Nov", equity: 16500, benchmark: 11300 },
    { date: "Dec", equity: 17800, benchmark: 11500 }
  ];

  const backtests = [
    {
      id: 1,
      name: "Mean Reversion Strategy",
      period: "2024 Q1",
      status: "completed",
      returns: 78.0,
      sharpe: 2.1,
      maxDrawdown: -8.2,
      winRate: 68.5,
      trades: 342
    },
    {
      id: 2,
      name: "Momentum Breakout",
      period: "2024 Q1",
      status: "completed",
      returns: 45.3,
      sharpe: 1.5,
      maxDrawdown: -12.1,
      winRate: 58.3,
      trades: 218
    },
    {
      id: 3,
      name: "Market Making",
      period: "2024 Q1",
      status: "completed",
      returns: 89.2,
      sharpe: 2.4,
      maxDrawdown: -6.5,
      winRate: 71.2,
      trades: 1247
    }
  ];

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-popover border border-border rounded-lg p-3 shadow-lg">
          <p className="text-sm font-medium mb-1">{payload[0].payload.date}</p>
          <p className="text-sm text-green-500">Strategy: ${payload[0].value.toLocaleString()}</p>
          <p className="text-sm text-muted-foreground">Benchmark: ${payload[1].value.toLocaleString()}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 p-6 max-w-full">
        {/* Configuration Panel */}
        <div className={`xl:col-span-4 space-y-4 ${showConfig ? '' : 'hidden xl:block'}`}>
          <div className="bg-card rounded-lg border border-border p-6 sticky top-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Settings2 className="w-5 h-5" />
                <h3>Backtest Configuration</h3>
              </div>
              <button
                onClick={() => setShowConfig(!showConfig)}
                className="xl:hidden p-2 hover:bg-accent rounded-lg"
              >
                <ChevronDown className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-sm mb-2 block">Strategy</label>
                <select
                  value={configData.strategy}
                  onChange={(e) => setConfigData({...configData, strategy: e.target.value})}
                  className="w-full px-3 py-2 bg-input-background border border-border rounded-lg"
                >
                  <option value="mean-reversion">Mean Reversion</option>
                  <option value="momentum">Momentum Breakout</option>
                  <option value="market-making">Market Making</option>
                  <option value="arbitrage">Arbitrage</option>
                </select>
              </div>

              <div>
                <label className="text-sm mb-2 block">Trading Pair</label>
                <select
                  value={configData.symbol}
                  onChange={(e) => setConfigData({...configData, symbol: e.target.value})}
                  className="w-full px-3 py-2 bg-input-background border border-border rounded-lg"
                >
                  <option value="BTC/USD">BTC/USD</option>
                  <option value="ETH/USD">ETH/USD</option>
                  <option value="BTC/ETH">BTC/ETH</option>
                </select>
              </div>

              <div>
                <label className="text-sm mb-2 block">Timeframe</label>
                <div className="grid grid-cols-4 gap-2">
                  {['1m', '5m', '15m', '1h', '4h', '1d'].map((tf) => (
                    <button
                      key={tf}
                      onClick={() => setConfigData({...configData, timeframe: tf})}
                      className={`px-3 py-2 rounded-lg text-sm transition-colors ${
                        configData.timeframe === tf
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-input-background hover:bg-accent'
                      }`}
                    >
                      {tf}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm mb-2 block">Start Date</label>
                  <input
                    type="date"
                    value={configData.startDate}
                    onChange={(e) => setConfigData({...configData, startDate: e.target.value})}
                    className="w-full px-3 py-2 bg-input-background border border-border rounded-lg"
                  />
                </div>
                <div>
                  <label className="text-sm mb-2 block">End Date</label>
                  <input
                    type="date"
                    value={configData.endDate}
                    onChange={(e) => setConfigData({...configData, endDate: e.target.value})}
                    className="w-full px-3 py-2 bg-input-background border border-border rounded-lg"
                  />
                </div>
              </div>

              <div>
                <label className="text-sm mb-2 block">Initial Capital ($)</label>
                <input
                  type="number"
                  value={configData.initialCapital}
                  onChange={(e) => setConfigData({...configData, initialCapital: Number(e.target.value)})}
                  className="w-full px-3 py-2 bg-input-background border border-border rounded-lg"
                />
              </div>

              <div>
                <label className="text-sm mb-2 block">Position Size (%)</label>
                <input
                  type="range"
                  min="1"
                  max="100"
                  value={configData.positionSize}
                  onChange={(e) => setConfigData({...configData, positionSize: Number(e.target.value)})}
                  className="w-full"
                />
                <div className="text-sm text-muted-foreground mt-1">{configData.positionSize}%</div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm mb-2 block">Stop Loss (%)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={configData.stopLoss}
                    onChange={(e) => setConfigData({...configData, stopLoss: Number(e.target.value)})}
                    className="w-full px-3 py-2 bg-input-background border border-border rounded-lg"
                  />
                </div>
                <div>
                  <label className="text-sm mb-2 block">Take Profit (%)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={configData.takeProfit}
                    onChange={(e) => setConfigData({...configData, takeProfit: Number(e.target.value)})}
                    className="w-full px-3 py-2 bg-input-background border border-border rounded-lg"
                  />
                </div>
              </div>

              <button className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-opacity">
                <Play className="w-4 h-4" />
                Run Backtest
              </button>
            </div>
          </div>
        </div>

        {/* Results Panel */}
        <div className="xl:col-span-8 space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1>Backtest Results</h1>
              <p className="text-sm text-muted-foreground mt-1">
                Historical strategy performance analysis
              </p>
            </div>
            <button
              onClick={() => setShowConfig(!showConfig)}
              className="xl:hidden flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg"
            >
              <Settings2 className="w-4 h-4" />
              Configure
            </button>
          </div>

          {/* Equity Curve */}
        <div className="bg-card rounded-lg border border-border p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3>Equity Curve</h3>
              <p className="text-xs text-muted-foreground">Strategy vs Benchmark</p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-primary" />
                <span className="text-sm">Strategy</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-muted-foreground" />
                <span className="text-sm">Benchmark</span>
              </div>
            </div>
          </div>

          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={equityCurveData}>
              <defs>
                <linearGradient id="colorStrategy" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="var(--primary)" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey="date"
                stroke="var(--muted-foreground)"
                tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
              />
              <YAxis
                stroke="var(--muted-foreground)"
                tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
              />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="equity"
                stroke="var(--primary)"
                strokeWidth={2}
                fill="url(#colorStrategy)"
              />
              <Line
                type="monotone"
                dataKey="benchmark"
                stroke="var(--muted-foreground)"
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

          {/* Backtest Results */}
          <div>
            <h2 className="mb-4">Historical Backtests</h2>
          <div className="grid gap-4">
            {backtests.map((backtest) => (
              <div key={backtest.id} className="bg-card rounded-lg border border-border p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3>{backtest.name}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <Calendar className="w-3 h-3 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground">{backtest.period}</span>
                      <span className="px-2 py-0.5 bg-green-500/10 text-green-500 text-xs rounded-full">
                        Completed
                      </span>
                    </div>
                  </div>
                  <button className="p-2 hover:bg-accent rounded-lg transition-colors">
                    <Download className="w-4 h-4" />
                  </button>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <div className="bg-background rounded-lg p-3">
                    <div className="text-xs text-muted-foreground mb-1">Total Returns</div>
                    <div className="text-lg text-green-500 flex items-center gap-1">
                      <TrendingUp className="w-4 h-4" />
                      +{backtest.returns}%
                    </div>
                  </div>
                  <div className="bg-background rounded-lg p-3">
                    <div className="text-xs text-muted-foreground mb-1">Sharpe Ratio</div>
                    <div className="text-lg">{backtest.sharpe}</div>
                  </div>
                  <div className="bg-background rounded-lg p-3">
                    <div className="text-xs text-muted-foreground mb-1">Max Drawdown</div>
                    <div className="text-lg text-red-500">{backtest.maxDrawdown}%</div>
                  </div>
                  <div className="bg-background rounded-lg p-3">
                    <div className="text-xs text-muted-foreground mb-1">Win Rate</div>
                    <div className="text-lg">{backtest.winRate}%</div>
                  </div>
                  <div className="bg-background rounded-lg p-3">
                    <div className="text-xs text-muted-foreground mb-1">Total Trades</div>
                    <div className="text-lg">{backtest.trades}</div>
                  </div>
                </div>

                <div className="mt-4 flex gap-2">
                  <button className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm hover:opacity-90 transition-opacity">
                    View Details
                  </button>
                  <button className="px-4 py-2 border border-border rounded-lg text-sm hover:bg-accent transition-colors">
                    Clone & Modify
                  </button>
                </div>
              </div>
            ))}
          </div>
          </div>
        </div>
      </div>
    </div>
  );
}
