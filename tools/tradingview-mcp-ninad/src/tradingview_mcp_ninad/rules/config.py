"""Pydantic model for rules.json — schema matches the original project exactly."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BiasCriteria(BaseModel):
    """Conditions for each directional bias; each is a list of human-readable
    statements that the model evaluates against indicator readings."""
    bullish: list[str] = Field(default_factory=list)
    bearish: list[str] = Field(default_factory=list)
    neutral: list[str] = Field(default_factory=list)


class RulesConfig(BaseModel):
    """Validated representation of a user's ``rules.json``.

    The field names and types are a 1:1 match with the original JSON schema
    so the same ``rules.json`` works across the Node and Python servers.
    """
    watchlist: list[str] = Field(default_factory=list)
    default_timeframe: str = "240"
    bias_criteria: BiasCriteria = Field(default_factory=BiasCriteria)
    risk_rules: list[str] = Field(default_factory=list)
    notes: str = ""
