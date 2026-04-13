"""
Intelligence Suite — Risk Allocator
======================================
Distributes risk budget across multiple accounts based on balance
proportions or manually specified weights.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class RiskAllocator:
    """Allocates risk proportionally across multiple trading accounts."""

    def allocate(
        self,
        accounts: dict[str, dict[str, Any]],
        total_risk_pct: float = 2.0,
        manual_weights: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """
        Calculate per-account risk allocation.

        Parameters
        ----------
        accounts : dict
            Mapping of account_label -> {balance, equity, ...}.
        total_risk_pct : float
            Total risk as a percentage of aggregate equity (e.g. 2.0 = 2%).
        manual_weights : dict, optional
            Mapping of account_label -> weight (0-1). If provided, these
            weights override proportional-by-balance allocation.

        Returns
        -------
        dict with total_equity, total_risk_amount, and per-account allocations.
        """
        if not accounts:
            return {
                "total_equity": 0,
                "total_risk_pct": total_risk_pct,
                "total_risk_amount": 0,
                "allocations": {},
            }

        # Aggregate equity
        equities: dict[str, float] = {}
        for label, info in accounts.items():
            if isinstance(info, dict) and "error" not in info:
                equities[label] = float(info.get("equity", info.get("balance", 0)))
            else:
                equities[label] = 0.0

        total_equity = sum(equities.values())
        total_risk_amount = total_equity * (total_risk_pct / 100.0)

        # Determine weights
        if manual_weights:
            # Normalize manual weights to sum to 1
            weight_sum = sum(manual_weights.values())
            if weight_sum <= 0:
                weights = {label: 1.0 / len(equities) for label in equities}
            else:
                weights = {
                    label: manual_weights.get(label, 0) / weight_sum
                    for label in equities
                }
        else:
            # Proportional by equity
            if total_equity > 0:
                weights = {label: eq / total_equity for label, eq in equities.items()}
            else:
                weights = {label: 1.0 / max(len(equities), 1) for label in equities}

        # Build allocations
        allocations: dict[str, dict] = {}
        for label in equities:
            weight = weights.get(label, 0)
            acct_equity = equities[label]
            risk_amount = total_risk_amount * weight
            risk_pct_of_account = (
                (risk_amount / acct_equity * 100) if acct_equity > 0 else 0
            )

            allocations[label] = {
                "equity": round(acct_equity, 2),
                "weight": round(weight, 4),
                "risk_amount": round(risk_amount, 2),
                "risk_pct_of_account": round(risk_pct_of_account, 2),
                "max_position_size": round(risk_amount, 2),
            }

        result = {
            "total_equity": round(total_equity, 2),
            "total_risk_pct": total_risk_pct,
            "total_risk_amount": round(total_risk_amount, 2),
            "allocation_method": "manual" if manual_weights else "proportional",
            "allocations": allocations,
        }

        logger.info(
            f"Risk allocated: total_equity={total_equity:.2f}, "
            f"risk={total_risk_amount:.2f} ({total_risk_pct}%) "
            f"across {len(allocations)} accounts"
        )
        return result
