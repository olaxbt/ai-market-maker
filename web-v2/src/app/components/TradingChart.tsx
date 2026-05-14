import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceDot, Legend } from "recharts";
import { TrendingUp, TrendingDown } from "lucide-react";

interface TradeMarker {
  time: string;
  price: number;
  type: "long" | "short";
  label: string;
}

interface TradingChartProps {
  data: Array<{ time: string; price: number }>;
  markers?: TradeMarker[];
}

export default function TradingChart({ data, markers = [] }: TradingChartProps) {
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-popover border border-border rounded-lg p-3 shadow-lg">
          <p className="text-sm font-medium">{payload[0].payload.time}</p>
          <p className="text-sm text-muted-foreground">
            Price: ${payload[0].value.toFixed(2)}
          </p>
        </div>
      );
    }
    return null;
  };

  const CustomDot = (props: any) => {
    const { cx, cy, payload } = props;
    const marker = markers.find(m => m.time === payload.time);

    if (!marker) return null;

    return (
      <g>
        <circle
          cx={cx}
          cy={cy}
          r={6}
          fill={marker.type === "long" ? "#10b981" : "#ef4444"}
          stroke="#fff"
          strokeWidth={2}
        />
        <foreignObject
          x={cx - 12}
          y={cy - 32}
          width={24}
          height={24}
        >
          {marker.type === "long" ? (
            <TrendingUp className="w-6 h-6 text-green-500" />
          ) : (
            <TrendingDown className="w-6 h-6 text-red-500" />
          )}
        </foreignObject>
      </g>
    );
  };

  return (
    <div className="bg-card rounded-lg border border-border p-4">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3>BTC/USD</h3>
          <p className="text-xs text-muted-foreground">Live Market Data</p>
        </div>
        <div className="flex gap-4 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-green-500" />
            <span>Long Entry</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500" />
            <span>Short Entry</span>
          </div>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="time"
            stroke="var(--muted-foreground)"
            tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
          />
          <YAxis
            stroke="var(--muted-foreground)"
            tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
            domain={['dataMin - 100', 'dataMax + 100']}
          />
          <Tooltip content={<CustomTooltip />} />
          <Line
            type="monotone"
            dataKey="price"
            stroke="var(--primary)"
            strokeWidth={2}
            dot={<CustomDot />}
            activeDot={{ r: 8 }}
          />
        </LineChart>
      </ResponsiveContainer>

      {/* Trade Markers Legend */}
      {markers.length > 0 && (
        <div className="mt-4 pt-4 border-t border-border">
          <h4 className="text-sm mb-2">Recent Trades</h4>
          <div className="space-y-2">
            {markers.map((marker, idx) => (
              <div key={idx} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  {marker.type === "long" ? (
                    <TrendingUp className="w-4 h-4 text-green-500" />
                  ) : (
                    <TrendingDown className="w-4 h-4 text-red-500" />
                  )}
                  <span className={marker.type === "long" ? "text-green-500" : "text-red-500"}>
                    {marker.label}
                  </span>
                </div>
                <div className="text-muted-foreground">
                  {marker.time} @ ${marker.price.toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
