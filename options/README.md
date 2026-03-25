# Options Strategies (Indian Market Focus)

This directory contains options strategies primarily targeting NSE/BSE derivatives.

## Structure

```
options/
├── strategies/          # Strategy implementation scripts
├── payoff_diagrams/     # Visual payoff charts for each strategy
├── greeks_analysis/     # Greeks tracking & analysis tools
├── chain_data/          # Option chain data snapshots (gitignored)
└── templates/           # Boilerplate for new strategies
```

## Common Strategies to Implement

### Non-Directional
- Iron Condor (weekly NIFTY/BANKNIFTY)
- Short Strangle with adjustments
- Iron Butterfly

### Directional
- Bull Call Spread / Bear Put Spread
- Ratio Spreads
- Synthetic positions

### Volatility
- Long Straddle (pre-event)
- Calendar Spreads
- VIX-based entries

### Expiry Day
- 0DTE strategies (NIFTY weekly expiry)
- Gamma scalping
- Pin risk management

## Indian Market Notes
- NIFTY/BANKNIFTY weekly expiry: Thursday
- FINNIFTY weekly expiry: Tuesday
- MIDCPNIFTY weekly expiry: Monday
- Lot sizes change periodically - check NSE circulars
- STT on exercised options is significantly higher than on squared-off positions
- F&O ban period: no fresh positions allowed when OI crosses 95% of MWPL
