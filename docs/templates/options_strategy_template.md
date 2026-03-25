# Options Strategy: [Name]

## Overview
- **Strategy Type**: [Iron Condor / Bull Call Spread / Straddle / Strangle / Butterfly / Calendar / Custom]
- **Underlying**: [NIFTY / BANKNIFTY / FINNIFTY / Stock]
- **Market**: NSE/BSE
- **Expiry Preference**: [Weekly / Monthly]
- **Version**: v1.0
- **Status**: [Research / Backtested / Paper Trading / Live]

## Strategy Logic
Describe when and why this strategy is deployed (market regime, IV conditions, etc.)

## Legs
| Leg | Action | Type | Strike Selection | Quantity |
|-----|--------|------|-----------------|----------|
| 1   | BUY/SELL | CE/PE | ATM/OTM+100/etc | |
| 2   | BUY/SELL | CE/PE | | |

## Entry Criteria
- **IV Rank/Percentile**:
- **Market condition**:
- **Time of entry**:
- **DTE (Days to Expiry)**:
- **Other filters**:

## Adjustment Rules
| Trigger | Action |
|---------|--------|
| Breach of upper breakeven | |
| Breach of lower breakeven | |
| Theta decay threshold | |
| IV spike/crush | |

## Exit Rules
- **Profit target**: (% of max profit)
- **Stop loss**: (% of premium or max loss)
- **Time-based**: (exit before expiry at X DTE)
- **Gamma risk cutoff**:

## Greeks at Entry
| Greek | Target Range |
|-------|-------------|
| Delta | |
| Gamma | |
| Theta | |
| Vega  | |

## Risk Management
- **Max capital per trade**:
- **Max positions simultaneously**:
- **Margin requirement**:
- **Max loss per trade**:

## Payoff Diagram
Reference: `options/payoff_diagrams/[filename]`

## Backtest Results (Indian Market)
| Metric | Value |
|--------|-------|
| Period | |
| Total Trades | |
| Win Rate | |
| Avg Profit (winners) | |
| Avg Loss (losers) | |
| Max Drawdown | |
| Avg ROI per trade | |
| Best performing expiry day | |

## Indian Market Considerations
- **NSE lot sizes**: [current lot size]
- **Margin requirements**: [SPAN + Exposure]
- **STT/CTT impact**: [note on Securities Transaction Tax]
- **Expiry day behavior**: [Thursday/last Thursday specifics]
- **Ban period handling**: [F&O ban list considerations]

## Changelog
| Date | Version | Change |
|------|---------|--------|
|      | v1.0    | Initial version |
