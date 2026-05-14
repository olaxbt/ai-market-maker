import { TrendingUp, TrendingDown, DollarSign, BarChart3, Clock } from "lucide-react";

interface InteractiveMessageProps {
  type?: "table" | "card" | "code";
  content: string;
  timestamp: string;
}

export default function InteractiveMessage({ type, content, timestamp }: InteractiveMessageProps) {
  if (type === "table" && content === "strategy-performance") {
    const strategies = [
      { name: "Market Making", status: "active", pnl: 2341, winRate: 68.5, trades: 142 },
      { name: "Arbitrage", status: "active", pnl: 1823, winRate: 71.2, trades: 89 },
      { name: "Mean Reversion", status: "paused", pnl: -245, winRate: 45.3, trades: 23 }
    ];

    return (
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <div className="p-4 border-b border-border bg-muted/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-primary" />
              <span className="font-medium">Active Strategy Performance</span>
            </div>
            <span className="text-xs text-muted-foreground">{timestamp}</span>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-muted/50 border-b border-border">
              <tr>
                <th className="px-4 py-3 text-left text-xs text-muted-foreground uppercase">Strategy</th>
                <th className="px-4 py-3 text-left text-xs text-muted-foreground uppercase">Status</th>
                <th className="px-4 py-3 text-right text-xs text-muted-foreground uppercase">PnL (24h)</th>
                <th className="px-4 py-3 text-right text-xs text-muted-foreground uppercase">Win Rate</th>
                <th className="px-4 py-3 text-right text-xs text-muted-foreground uppercase">Trades</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {strategies.map((strategy, idx) => (
                <tr key={idx} className="hover:bg-muted/20">
                  <td className="px-4 py-3 font-medium">{strategy.name}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded-full text-xs ${
                      strategy.status === "active"
                        ? "bg-green-500/10 text-green-500"
                        : "bg-muted text-muted-foreground"
                    }`}>
                      {strategy.status}
                    </span>
                  </td>
                  <td className={`px-4 py-3 text-right font-mono ${
                    strategy.pnl >= 0 ? "text-green-500" : "text-red-500"
                  }`}>
                    {strategy.pnl >= 0 ? "+" : ""}${strategy.pnl.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">{strategy.winRate}%</td>
                  <td className="px-4 py-3 text-right">{strategy.trades}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  if (type === "card" && content === "portfolio-stats") {
    return (
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <div className="p-4 border-b border-border bg-muted/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-primary" />
              <span className="font-medium">Portfolio Overview</span>
            </div>
            <span className="text-xs text-muted-foreground">{timestamp}</span>
          </div>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-background rounded-lg p-4 border border-border">
              <div className="text-xs text-muted-foreground mb-2">Total Balance</div>
              <div className="text-2xl font-mono mb-1">$124,567</div>
              <div className="flex items-center gap-1 text-sm text-green-500">
                <TrendingUp className="w-3 h-3" />
                <span>+4.2%</span>
              </div>
            </div>
            <div className="bg-background rounded-lg p-4 border border-border">
              <div className="text-xs text-muted-foreground mb-2">Today's PnL</div>
              <div className="text-2xl font-mono mb-1 text-green-500">+$3,919</div>
              <div className="flex items-center gap-1 text-sm text-muted-foreground">
                <Clock className="w-3 h-3" />
                <span>Last 24h</span>
              </div>
            </div>
            <div className="bg-background rounded-lg p-4 border border-border">
              <div className="text-xs text-muted-foreground mb-2">Win Rate</div>
              <div className="text-2xl font-mono mb-1">68.5%</div>
              <div className="text-sm text-muted-foreground">254 trades</div>
            </div>
            <div className="bg-background rounded-lg p-4 border border-border">
              <div className="text-xs text-muted-foreground mb-2">Risk Score</div>
              <div className="text-2xl font-mono mb-1">42/100</div>
              <div className="text-sm text-green-500">Low Risk</div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (type === "code") {
    return (
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <div className="p-4 border-b border-border bg-muted/30 flex items-center justify-between">
          <span className="text-sm font-medium">Code Example</span>
          <span className="text-xs text-muted-foreground">{timestamp}</span>
        </div>
        <div className="p-4 bg-[#1e1e1e] font-mono text-sm overflow-x-auto">
          <pre className="text-[#d4d4d4]">
{`// Market Making Strategy
const strategy = {
  spread: 0.002,
  orderSize: 1.0,
  maxInventory: 10.0
};

function placeOrders(midPrice) {
  const bid = midPrice * (1 - strategy.spread);
  const ask = midPrice * (1 + strategy.spread);

  exchange.placeLimitOrder('buy', bid, strategy.orderSize);
  exchange.placeLimitOrder('sell', ask, strategy.orderSize);
}`}
          </pre>
        </div>
      </div>
    );
  }

  return null;
}
