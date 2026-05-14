import React, { Crown, TrendingUp, TrendingDown, Medal } from "lucide-react";

interface Trader {
  rank: number;
  name: string;
  avatar: string;
  pnl: number;
  pnlChange: number;
  winRate: number;
  trades: number;
  volume: number;
  sharpe: number;
}

export default function LeaderboardView() {
  const traders: Trader[] = [
    {
      rank: 1,
      name: "QuantMaster",
      avatar: "QM",
      pnl: 245320,
      pnlChange: 12.5,
      winRate: 68.5,
      trades: 1247,
      volume: 8500000,
      sharpe: 2.3
    },
    {
      rank: 2,
      name: "AlphaSeeker",
      avatar: "AS",
      pnl: 198940,
      pnlChange: 8.3,
      winRate: 65.2,
      trades: 892,
      volume: 6200000,
      sharpe: 2.0
    },
    {
      rank: 3,
      name: "MarketMaker Pro",
      avatar: "MM",
      pnl: 182150,
      pnlChange: 15.7,
      winRate: 71.3,
      trades: 1089,
      volume: 7300000,
      sharpe: 2.4
    },
    {
      rank: 4,
      name: "FlowTrader",
      avatar: "FT",
      pnl: 168700,
      pnlChange: -3.2,
      winRate: 63.8,
      trades: 756,
      volume: 5100000,
      sharpe: 1.8
    },
    {
      rank: 5,
      name: "ArbitrageBot",
      avatar: "AB",
      pnl: 154500,
      pnlChange: 6.9,
      winRate: 69.1,
      trades: 1523,
      volume: 9200000,
      sharpe: 2.1
    },
    {
      rank: 6,
      name: "VolatilityKing",
      avatar: "VK",
      pnl: 142300,
      pnlChange: 4.5,
      winRate: 61.4,
      trades: 634,
      volume: 4800000,
      sharpe: 1.7
    },
    {
      rank: 7,
      name: "TrendFollower",
      avatar: "TF",
      pnl: 128900,
      pnlChange: -1.8,
      winRate: 58.7,
      trades: 543,
      volume: 4200000,
      sharpe: 1.5
    },
    {
      rank: 8,
      name: "ScalpMaster",
      avatar: "SM",
      pnl: 115600,
      pnlChange: 9.2,
      winRate: 72.3,
      trades: 2341,
      volume: 11500000,
      sharpe: 2.2
    }
  ];

  const getRankBadge = (rank: number) => {
    if (rank === 1) {
      return (
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-yellow-400 to-yellow-600 flex items-center justify-center">
          <Crown className="w-5 h-5 text-white" />
        </div>
      );
    } else if (rank === 2) {
      return (
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-gray-300 to-gray-500 flex items-center justify-center">
          <Medal className="w-5 h-5 text-white" />
        </div>
      );
    } else if (rank === 3) {
      return (
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center">
          <Medal className="w-5 h-5 text-white" />
        </div>
      );
    } else {
      return (
        <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center text-muted-foreground font-medium">
          #{rank}
        </div>
      );
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1>Trader Leaderboard</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Top performing traders in the last 30 days
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select className="px-4 py-2 bg-input-background border border-border rounded-lg text-sm">
              <option>Last 30 Days</option>
              <option>Last 7 Days</option>
              <option>All Time</option>
            </select>
          </div>
        </div>

        {/* Top 3 Podium */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {traders.slice(0, 3).map((trader) => (
            <div
              key={trader.rank}
              className={`bg-card rounded-lg border-2 p-6 text-center ${
                trader.rank === 1
                  ? "border-yellow-500"
                  : trader.rank === 2
                  ? "border-gray-400"
                  : "border-orange-500"
              }`}
            >
              <div className="flex justify-center mb-3">{getRankBadge(trader.rank)}</div>
              <div className="w-16 h-16 rounded-full bg-primary text-primary-foreground flex items-center justify-center mx-auto mb-3 text-xl">
                {trader.avatar}
              </div>
              <h3 className="mb-1">{trader.name}</h3>
              <div className="text-2xl text-green-500 mb-1">
                ${trader.pnl.toLocaleString()}
              </div>
              <div className="text-sm text-muted-foreground">{trader.winRate}% Win Rate</div>
            </div>
          ))}
        </div>

        {/* Full Leaderboard Table */}
        <div className="bg-card rounded-lg border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/50 border-b border-border">
                <tr>
                  <th className="px-6 py-3 text-left text-xs text-muted-foreground uppercase tracking-wider">
                    Rank
                  </th>
                  <th className="px-6 py-3 text-left text-xs text-muted-foreground uppercase tracking-wider">
                    Trader
                  </th>
                  <th className="px-6 py-3 text-right text-xs text-muted-foreground uppercase tracking-wider">
                    Total PnL
                  </th>
                  <th className="px-6 py-3 text-right text-xs text-muted-foreground uppercase tracking-wider">
                    Change
                  </th>
                  <th className="px-6 py-3 text-right text-xs text-muted-foreground uppercase tracking-wider">
                    Win Rate
                  </th>
                  <th className="px-6 py-3 text-right text-xs text-muted-foreground uppercase tracking-wider">
                    Trades
                  </th>
                  <th className="px-6 py-3 text-right text-xs text-muted-foreground uppercase tracking-wider">
                    Volume
                  </th>
                  <th className="px-6 py-3 text-right text-xs text-muted-foreground uppercase tracking-wider">
                    Sharpe
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {traders.map((trader) => (
                  <tr key={trader.rank} className="hover:bg-muted/30 transition-colors">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-3">
                        {getRankBadge(trader.rank)}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-primary text-primary-foreground flex items-center justify-center">
                          {trader.avatar}
                        </div>
                        <span className="font-medium">{trader.name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <span className="text-green-500 font-medium">
                        ${trader.pnl.toLocaleString()}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <div className={`flex items-center justify-end gap-1 ${
                        trader.pnlChange >= 0 ? "text-green-500" : "text-red-500"
                      }`}>
                        {trader.pnlChange >= 0 ? (
                          <TrendingUp className="w-4 h-4" />
                        ) : (
                          <TrendingDown className="w-4 h-4" />
                        )}
                        <span>{Math.abs(trader.pnlChange)}%</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <span>{trader.winRate}%</span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <span>{trader.trades.toLocaleString()}</span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <span>${(trader.volume / 1000000).toFixed(1)}M</span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <span>{trader.sharpe}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
