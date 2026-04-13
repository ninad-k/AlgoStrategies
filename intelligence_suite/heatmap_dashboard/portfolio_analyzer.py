"""
ReySentinel — Portfolio Analyzer
=========================================
Groups positions by asset type and calculates exposure, concentration risk (HHI).
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Symbol-to-asset-type classification
ASSET_TYPE_MAP: dict[str, str] = {
    # Crypto
    "BTCUSD": "crypto", "ETHUSD": "crypto", "LTCUSD": "crypto",
    "XRPUSD": "crypto", "SOLUSD": "crypto", "ADAUSD": "crypto",
    "DOTUSD": "crypto", "AVAXUSD": "crypto", "LINKUSD": "crypto",
    "BNBUSD": "crypto", "DOGEUSD": "crypto", "MATICUSD": "crypto",
    # Forex
    "EURUSD": "forex", "GBPUSD": "forex", "USDJPY": "forex",
    "AUDUSD": "forex", "USDCAD": "forex", "NZDUSD": "forex",
    "USDCHF": "forex", "EURGBP": "forex", "EURJPY": "forex",
    "GBPJPY": "forex",
    # Commodities
    "XAUUSD": "commodity", "XAGUSD": "commodity", "XBRUSD": "commodity",
    "XTIUSD": "commodity", "XNGUSD": "commodity",
    # Equity indices
    "US500": "equity", "US30": "equity", "USTEC": "equity",
    "DE40": "equity", "UK100": "equity", "JP225": "equity",
}

# Sector/correlation groupings
SECTOR_MAP: dict[str, str] = {
    "BTCUSD": "large_cap_crypto", "ETHUSD": "large_cap_crypto",
    "LTCUSD": "alt_crypto", "XRPUSD": "alt_crypto",
    "SOLUSD": "alt_crypto", "ADAUSD": "alt_crypto",
    "DOTUSD": "alt_crypto", "AVAXUSD": "alt_crypto",
    "LINKUSD": "defi_crypto", "MATICUSD": "defi_crypto",
    "EURUSD": "major_fx", "GBPUSD": "major_fx", "USDJPY": "major_fx",
    "AUDUSD": "commodity_fx", "NZDUSD": "commodity_fx", "USDCAD": "commodity_fx",
    "XAUUSD": "precious_metals", "XAGUSD": "precious_metals",
    "XBRUSD": "energy", "XTIUSD": "energy", "XNGUSD": "energy",
    "US500": "us_indices", "US30": "us_indices", "USTEC": "us_indices",
}


class PortfolioAnalyzer:
    """Analyzes portfolio positions for exposure, concentration, and sector risk."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def _classify_asset_type(self, symbol: str) -> str:
        """Return the asset type for a given symbol."""
        return ASSET_TYPE_MAP.get(symbol.upper(), "unknown")

    def _classify_sector(self, symbol: str) -> str:
        """Return the sector grouping for a given symbol."""
        return SECTOR_MAP.get(symbol.upper(), "other")

    def _calculate_hhi(self, exposures: dict[str, float], total: float) -> float:
        """
        Calculate the Herfindahl-Hirschman Index (HHI) for concentration risk.
        HHI ranges from 0 (perfectly diversified) to 10000 (single position).
        """
        if total <= 0:
            return 0.0
        shares = [(abs(v) / total) * 100.0 for v in exposures.values() if v != 0]
        return sum(s ** 2 for s in shares)

    def analyze(self, positions: list[dict]) -> dict:
        """
        Analyze a list of positions and return exposure metrics.

        Parameters
        ----------
        positions : list[dict]
            Each dict must have at least: symbol, volume, profit, price_current (or current_price).

        Returns
        -------
        dict with keys:
            total_exposure, per_asset_type_exposure, per_sector_exposure,
            per_symbol_exposure, concentration_risk, position_count, warnings
        """
        if not positions:
            return {
                "total_exposure": 0.0,
                "per_asset_type_exposure": {},
                "per_sector_exposure": {},
                "per_symbol_exposure": {},
                "concentration_risk": 0.0,
                "position_count": 0,
                "warnings": [],
            }

        per_symbol: dict[str, float] = {}
        per_asset_type: dict[str, float] = {}
        per_sector: dict[str, float] = {}
        total_exposure = 0.0
        warnings: list[str] = []

        for pos in positions:
            symbol = pos.get("symbol", "UNKNOWN")
            volume = float(pos.get("volume", 0))
            price = float(pos.get("price_current", pos.get("current_price", 0)))
            notional = volume * price

            asset_type = self._classify_asset_type(symbol)
            sector = self._classify_sector(symbol)

            per_symbol[symbol] = per_symbol.get(symbol, 0.0) + notional
            per_asset_type[asset_type] = per_asset_type.get(asset_type, 0.0) + notional
            per_sector[sector] = per_sector.get(sector, 0.0) + notional
            total_exposure += notional

        # Concentration risk (HHI)
        hhi = self._calculate_hhi(per_symbol, total_exposure)

        # Warnings
        if hhi > 2500:
            warnings.append(f"High concentration risk: HHI={hhi:.0f} (>2500)")
        for sym, val in per_symbol.items():
            if total_exposure > 0 and (val / total_exposure) > 0.40:
                pct = (val / total_exposure) * 100
                warnings.append(f"{sym} represents {pct:.1f}% of total exposure")

        # Convert to percentage breakdowns
        per_asset_type_pct = {
            k: {"notional": v, "pct": (v / total_exposure * 100) if total_exposure > 0 else 0}
            for k, v in per_asset_type.items()
        }
        per_sector_pct = {
            k: {"notional": v, "pct": (v / total_exposure * 100) if total_exposure > 0 else 0}
            for k, v in per_sector.items()
        }
        per_symbol_pct = {
            k: {"notional": v, "pct": (v / total_exposure * 100) if total_exposure > 0 else 0}
            for k, v in per_symbol.items()
        }

        result = {
            "total_exposure": round(total_exposure, 2),
            "per_asset_type_exposure": per_asset_type_pct,
            "per_sector_exposure": per_sector_pct,
            "per_symbol_exposure": per_symbol_pct,
            "concentration_risk": round(hhi, 2),
            "position_count": len(positions),
            "warnings": warnings,
        }

        logger.info(
            f"Portfolio analyzed: {len(positions)} positions, "
            f"total_exposure={total_exposure:.2f}, HHI={hhi:.0f}"
        )
        return result
