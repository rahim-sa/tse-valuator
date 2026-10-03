"""
Core DCF math: multi-year FCF projection, terminal value, and
discounting to present value. All pure functions over plain numbers --
no data fetching, no LLM involvement. Every number here is directly
traceable to an explicit formula.
"""

from __future__ import annotations


def project_fcf(base_fcf: float, growth_rates: list[float]) -> list[float]:
    """
    Projects FCF forward, one year per growth rate given.
    growth_rates[0] is applied to base_fcf to get year 1, etc.
    """
    projected = []
    current = base_fcf
    for g in growth_rates:
        current = current * (1 + g)
        projected.append(current)
    return projected


def terminal_value(final_year_fcf: float, terminal_growth_rate: float, discount_rate: float) -> float:
    """Gordon growth terminal value, as of the END of the final projected year."""
    if discount_rate <= terminal_growth_rate:
        raise ValueError("discount_rate must exceed terminal_growth_rate for a finite terminal value")
    next_year_fcf = final_year_fcf * (1 + terminal_growth_rate)
    return next_year_fcf / (discount_rate - terminal_growth_rate)


def present_value(cash_flows: list[float], discount_rate: float) -> float:
    """PV of a list of cash flows, cash_flows[0] received at end of year 1."""
    return sum(cf / (1 + discount_rate) ** (i + 1) for i, cf in enumerate(cash_flows))


def enterprise_value(
    base_fcf: float,
    growth_rates: list[float],
    terminal_growth_rate: float,
    discount_rate: float,
) -> dict:
    """
    Full DCF enterprise value: PV of explicit-period FCFs + PV of
    terminal value. Returns a breakdown dict, not just one number, so
    every component is inspectable/auditable.
    """
    projected = project_fcf(base_fcf, growth_rates)
    pv_explicit = present_value(projected, discount_rate)

    tv = terminal_value(projected[-1], terminal_growth_rate, discount_rate)
    n_years = len(growth_rates)
    pv_terminal = tv / (1 + discount_rate) ** n_years

    return {
        "projected_fcf": projected,
        "pv_explicit_period": pv_explicit,
        "terminal_value_undiscounted": tv,
        "pv_terminal_value": pv_terminal,
        "enterprise_value": pv_explicit + pv_terminal,
    }