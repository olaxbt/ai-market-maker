import { useState } from "react";
import { ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area } from "recharts";
import { TrendingUp, TrendingDown, Maximize2, Download, Eye, EyeOff } from "lucide-react";

interface TradeMarker {
  time: string;
  price: number;
  type: "long" | "short";
  label: string;
}

interface ChartData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface AdvancedTradingChartProps {
  data: ChartData[];
  markers?: TradeMarker[];
}

export default function AdvancedTradingChart({ data, markers = [] }: AdvancedTradingChartProps) {
  const [showVolume, setShowVolume] = useState(true);
  const [showMarkers, setShowMarkers] = useState(true);
  const [timeframe, setTimeframe] = useState("1H");

  const currentPrice = data[data.length - 1]?.close || 0;
  const previousPrice = data[data.length - 2]?.close || 0;
  const priceChange = currentPrice - previousPrice;
  const priceChangePercent = (priceChange / previousPrice) * 100;

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-popover border border-border rounded-lg p-3 shadow-lg">
          <div className="text-xs text-muted-foreground mb-2">{data.time}</div>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">Open:</span>
              <span className="font-mono">${data.open.toFixed(2)}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">High:</span>
              <span className="font-mono text-green-500">${data.high.toFixed(2)}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">Low:</span>
              <span className="font-mono text-red-500">${data.low.toFixed(2)}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">Close:</span>
              <span className="font-mono">${data.close.toFixed(2)}</span>
            </div>
            {showVolume && (
              <div className="flex justify-between gap-4 pt-1 border-t border-border">
                <span className="text-muted-foreground">Volume:</span>
                <span className="font-mono">{(data.volume / 1000).toFixed(1)}K</span>
              </div>
            )}
          </div>
        </div>
      );
    }
    return null;
  };

  const CustomDot = (props: any) => {
    if (!showMarkers) return null;

    const { cx, cy, payload } = props;
    const marker = markers.find(m => m.time === payload.time);

    if (!marker) return null;

    return (
      <g>
        <circle
          cx={cx}
          cy={cy}
          r={8}
          fill={marker.type === "long" ? "#10b981" : "#ef4444"}
          stroke="#fff"
          strokeWidth={2}
        />
        {marker.type === "long" ? (
          <path
            d={`M ${cx - 3} ${cy} L ${cx} ${cy - 3} L ${cx + 3} ${cy} Z`}
            fill="#fff"
          />
        ) : (
          <path
            d={`M ${cx - 3} ${cy} L ${cx} ${cy + 3} L ${cx + 3} ${cy} Z`}
            fill="#fff"
          />
        )}
      </g>
    );
  };

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      {/* Chart Header */}
      <div className="border-b border-border p-4">
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h3>BTC/USD</h3>
              <span className="px-2 py-1 bg-muted rounded text-xs">Spot</span>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-3xl font-mono">${currentPrice.toFixed(2)}</div>
              <div className={`flex items-center gap-1 ${priceChange >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                {priceChange >= 0 ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
                <span className="text-xl font-mono">{priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)}</span>
                <span className="text-sm">({priceChangePercent >= 0 ? '+' : ''}{priceChangePercent.toFixed(2)}%)</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowMarkers(!showMarkers)}
              className={`p-2 rounded-lg transition-colors ${
                showMarkers ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-accent'
              }`}
              title={showMarkers ? "Hide trade markers" : "Show trade markers"}
            >
              {showMarkers ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
            </button>
            <button className="p-2 rounded-lg hover:bg-accent transition-colors">
              <Download className="w-4 h-4" />
            </button>
            <button className="p-2 rounded-lg hover:bg-accent transition-colors">
              <Maximize2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Timeframe Selector */}
        <div className="flex items-center gap-2">
          {['1m', '5m', '15m', '1H', '4H', '1D', '1W'].map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-3 py-1.5 rounded text-sm transition-colors ${
                timeframe === tf
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-accent'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div className="p-4">
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={data}>
            <defs>
              <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="var(--primary)" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="time"
              stroke="var(--muted-foreground)"
              tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
              height={40}
            />
            <YAxis
              yAxisId="price"
              orientation="right"
              stroke="var(--muted-foreground)"
              tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
              domain={['dataMin - 100', 'dataMax + 100']}
              width={80}
            />
            {showVolume && (
              <YAxis
                yAxisId="volume"
                orientation="left"
                stroke="var(--muted-foreground)"
                tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
                width={60}
              />
            )}
            <Tooltip content={<CustomTooltip />} />

            {showVolume && (
              <Bar
                yAxisId="volume"
                dataKey="volume"
                fill="var(--muted)"
                opacity={0.3}
                radius={[4, 4, 0, 0]}
              />
            )}

            <Area
              yAxisId="price"
              type="monotone"
              dataKey="close"
              stroke="var(--primary)"
              strokeWidth={2}
              fill="url(#colorPrice)"
              dot={<CustomDot />}
              activeDot={{ r: 6 }}
            />

            <Line
              yAxisId="price"
              type="monotone"
              dataKey="high"
              stroke="#10b981"
              strokeWidth={1}
              dot={false}
              strokeDasharray="3 3"
            />

            <Line
              yAxisId="price"
              type="monotone"
              dataKey="low"
              stroke="#ef4444"
              strokeWidth={1}
              dot={false}
              strokeDasharray="3 3"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Chart Footer - Order Book Preview & Stats */}
      <div className="border-t border-border p-4 grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-background rounded-lg p-3">
          <div className="text-xs text-muted-foreground mb-1">24h High</div>
          <div className="text-green-500 font-mono">${Math.max(...data.map(d => d.high)).toFixed(2)}</div>
        </div>
        <div className="bg-background rounded-lg p-3">
          <div className="text-xs text-muted-foreground mb-1">24h Low</div>
          <div className="text-red-500 font-mono">${Math.min(...data.map(d => d.low)).toFixed(2)}</div>
        </div>
        <div className="bg-background rounded-lg p-3">
          <div className="text-xs text-muted-foreground mb-1">24h Volume</div>
          <div className="font-mono">{(data.reduce((sum, d) => sum + d.volume, 0) / 1000000).toFixed(2)}M</div>
        </div>
        <div className="bg-background rounded-lg p-3">
          <div className="text-xs text-muted-foreground mb-1">Open Interest</div>
          <div className="font-mono">$8.4B</div>
        </div>
      </div>

      {/* Trade Markers List */}
      {showMarkers && markers.length > 0 && (
        <div className="border-t border-border p-4">
          <h4 className="text-sm mb-3 flex items-center gap-2">
            <span>Recent Trade Signals</span>
            <span className="px-2 py-0.5 bg-muted rounded-full text-xs">{markers.length}</span>
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {markers.map((marker, idx) => (
              <div key={idx} className={`flex items-center justify-between p-3 rounded-lg border ${
                marker.type === "long"
                  ? "bg-green-500/5 border-green-500/20"
                  : "bg-red-500/5 border-red-500/20"
              }`}>
                <div className="flex items-center gap-2">
                  {marker.type === "long" ? (
                    <div className="w-6 h-6 rounded-full bg-green-500 flex items-center justify-center">
                      <TrendingUp className="w-3.5 h-3.5 text-white" />
                    </div>
                  ) : (
                    <div className="w-6 h-6 rounded-full bg-red-500 flex items-center justify-center">
                      <TrendingDown className="w-3.5 h-3.5 text-white" />
                    </div>
                  )}
                  <div>
                    <div className={`text-sm font-medium ${marker.type === "long" ? "text-green-500" : "text-red-500"}`}>
                      {marker.label}
                    </div>
                    <div className="text-xs text-muted-foreground">{marker.time}</div>
                  </div>
                </div>
                <div className="text-sm font-mono">${marker.price.toFixed(2)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
