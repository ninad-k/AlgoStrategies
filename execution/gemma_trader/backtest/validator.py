"""
backtest/validator.py — OOS gating for candidate rule changes.

Rule (v1, conservative):
  expectancy_oos >= baseline.expectancy_oos * 1.05   AND
  max_dd_oos     <= baseline.max_dd_oos               AND
  trades_oos     >= 100
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from .engine import run_backtest
from .rules_loader import apply_proposal


MIN_TRADES = 100
EXPECTANCY_MULT = 1.05


@dataclass
class ValidationVerdict:
    accepted: bool
    reason: str
    oos_baseline: dict
    oos_candidate: dict


def validate_candidate(df_oos, symbol: str, rules_block: dict,
                       proposal: dict, baseline_oos: dict) -> ValidationVerdict:
    """
    Apply a single proposal on top of rules_block, rerun OOS backtest, compare.
    """
    # Build a candidate rules block by patching the proposal.
    candidate = copy.deepcopy(rules_block)
    # apply_proposal operates on a full rules dict with symbols[...] — build
    # a minimal wrapper so we can reuse the helper.
    wrapper = {"symbols": {symbol: candidate}}
    if not apply_proposal(wrapper, symbol, proposal["path"], proposal["to"]):
        return ValidationVerdict(False, f"bad path: {proposal['path']}",
                                 baseline_oos, {})
    candidate = wrapper["symbols"][symbol]

    candidate_oos = run_backtest(df_oos, symbol, candidate)

    if candidate_oos["trades"] < MIN_TRADES:
        return ValidationVerdict(False,
            f"insufficient OOS trades ({candidate_oos['trades']} < {MIN_TRADES})",
            baseline_oos, candidate_oos)

    base_exp = float(baseline_oos.get("expectancy_r", 0.0))
    cand_exp = float(candidate_oos.get("expectancy_r", 0.0))
    if cand_exp < base_exp * EXPECTANCY_MULT:
        return ValidationVerdict(False,
            f"expectancy regression ({cand_exp:.4f} < {base_exp:.4f} * {EXPECTANCY_MULT})",
            baseline_oos, candidate_oos)

    base_dd = float(baseline_oos.get("max_dd_r", 0.0))
    cand_dd = float(candidate_oos.get("max_dd_r", 0.0))
    if cand_dd > base_dd and base_dd > 0:
        return ValidationVerdict(False,
            f"drawdown regression ({cand_dd:.4f} > {base_dd:.4f})",
            baseline_oos, candidate_oos)

    return ValidationVerdict(True, "passed OOS gate", baseline_oos, candidate_oos)
