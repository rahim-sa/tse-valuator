"""Enterprise value -> equity value -> per-share value bridge."""

from __future__ import annotations


def equity_value(enterprise_value_: float, total_debt: float, cash_and_equivalents: float) -> float:
    return enterprise_value_ - total_debt + cash_and_equivalents


def value_per_share(equity_value_: float, shares_outstanding: float) -> float:
    if shares_outstanding <= 0:
        raise ValueError("shares_outstanding must be positive")
    return equity_value_ / shares_outstanding