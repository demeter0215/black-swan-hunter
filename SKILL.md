---
name: black-swan-hunter
description: Run a V5 black-swan hunting workflow for crypto crash/rebound setups with layered filters (volatility, audit/news, liquidation structure, MM trap checks, and execution confirmation). Use when users ask for flash-crash scans, deep single-symbol diagnosis, liquidation-driven entries, or risk-managed rebound plans. Integrate Binance Skills Hub tools such as spot, query-token-audit, query-token-info, trading-signal, crypto-market-rank, and query-address-info.
---

# Black Swan Hunter (V5)

## Command Set

### `/scan_v5`
Scan a symbol list for volatility anomalies, then rank by V5 score.

Required input:
- `symbols` (for example: `BTCUSDT,ETHUSDT,SOLUSDT`)

Optional input:
- `interval` default `5m`
- `lookback` default `50`
- `top_n` default `5`

### `/hunt_v5 <symbol>`
Run full L1-L5 diagnosis for one symbol and output one of:
- `BUY`
- `WATCH`
- `FADE`
- `NO_TRADE`

### `/mm_check <symbol>`
Check funding/open-interest/liquidation asymmetry for squeeze-trap risk.

### `/liquid_stream`
Start liquidation stream monitor (`!forceOrder@arr`) and persist rolling events.

## V5 Layers

### L1 Volatility Adaptive
Compute ATR(5m) and trigger when move exceeds configured ATR multiple.

### L2 Intelligence Arbiter
Call external skills in this order:
1. `query-token-audit` for contract/scam risk.
2. `query-token-info` for token metadata and sanity checks.
3. `trading-signal` for smart-money context.
4. Optional external news tools (`OpenNews`/`OpenTwitter`) only when previous checks are uncertain.

Hard rule:
- Any severe audit/security red flag -> `FADE`.

### L3 Blood Stream Confirmation
Require a structural flush signal:
- price drawdown + OI drop + liquidation burst.

### L4 MM Lens and Circuit Breaker
Identify squeeze traps using funding and short-side crowding proxies.

Critical Risk States:
- **`SQUEEZE_TRAP`**: If funding_rate < -0.002 (-0.2%) AND OI is growing. **Action: AVOID / DO NOT SHORT.**
- **`LIQUIDATION_CASCADE`**: If funding_rate > 0.002 (+0.2%) AND OI is growing. **Action: AVOID / DO NOT LONG.**
- **`FADE` (Mean Reversion)**: Only when move is parabolic BUT OI starts dropping AND RSI(15m) shows exhaustion.
- If none of the above, return `WATCH` or `NO_TRADE`.

### L5 Execution Confirmation
Only allow entry when one of these confirms:
- lower-wick rejection
- VWAP reclaim
- exhaustion candle pattern

Always return:
- entry
- stop
- tp ladder
- **Dextrader Critique (Mandatory)**: A dynamic, sharp-tongued live commentary based on the current metrics. No templates. Use current price move, funding rate, or OI to mock/praise the trade setup. (e.g. "-0.3% funding? The shorts are being incinerated and you want to join the barbecue? Move on.")
