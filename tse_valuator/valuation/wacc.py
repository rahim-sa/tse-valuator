"""
WACC (weighted average cost of capital) calculation.

All inputs are explicit parameters -- this module does no data
fetching itself. Risk-free rate, beta, and cost of debt are treated as
analyst-supplied assumptions (see module docstring in country_risk_client.py
for why: these are periodic, judgment-based inputs in real DCF practice,
not high-frequency data).
"""

from __future__ import annotations


def cost_of_equity(risk_free_rate: float, beta: float, equity_risk_premium: float) -> float:
    """CAPM: Re = Rf + beta * ERP"""
    return risk_free_rate + beta * equity_risk_premium


def wacc(
    cost_of_equity_: float,
    cost_of_debt: float,
    tax_rate: float,
    weight_equity: float,
    weight_debt: float,
) -> float:
    """
    WACC = We*Re + Wd*Rd*(1-tax_rate)
    Caller must ensure weight_equity + weight_debt == 1.0 (not enforced
    here to keep this a pure, simple calculation -- validate upstream).
    """
    after_tax_cost_of_debt = cost_of_debt * (1 - tax_rate)
    return weight_equity * cost_of_equity_ + weight_debt * after_tax_cost_of_debt