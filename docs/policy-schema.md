## Policy Configuration

Trading policies are defined in JSON files under the `config/` folder.

- Default: `config/policy.default.json`
- Example with comments: `config/policy.example.json`

Only the keys inside the top-level `"policy"` object are used.

### Available Fields

| Key                          | Type          | Default   | Description |
|-----------------------------|---------------|-----------|-------------|
| `portfolio_budget_usd`      | number        | 5000      | Base portfolio size used for allocation |
| `risk_position_cap_usd`     | number        | 1000      | Maximum USD allocation per symbol |
| `max_leverage`              | number        | 4         | Maximum gross leverage (1–100) |
| `allows_short`              | boolean       | false     | Allow short positions. If `false`, bearish signals result in HOLD |
| `stop_loss_pct`             | number        | 0.03      | Stop loss as fraction of entry price |
| `take_profit_pct`           | number        | 0.08      | Take profit as fraction of entry price |
| `min_confidence_directional`| number        | 0.45      | Minimum confidence required to open directional trades (0–1) |
| `trade_cooldown_bars`       | integer       | 48        | Minimum bars to wait between trades on the same symbol |
| `bull_exposure_floor`       | number        | 0.6       | Minimum exposure to hold during bullish regime (0–1) |
| `bear_exposure_cap`         | number        | 0.15      | Maximum exposure allowed during bearish regime (0–1) |
| `risk_max_drawdown_stop`    | number \| null| 0.2       | Portfolio-level drawdown stop (set to `null` to disable) |
| `risk_kill_switch_cooldown_bars` | integer  | 240       | Cooldown period in bars after drawdown stop is triggered |

### Notes

- All percentage values are expressed as fractions (e.g. `0.03` = 3%).
- `risk_max_drawdown_stop` can be disabled by setting it to `null`.
- See `config/policy.example.json` for a well-commented example.
