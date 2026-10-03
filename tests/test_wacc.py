import pytest
from tse_valuator.valuation.wacc import cost_of_equity, wacc


def test_cost_of_equity_capm():
    result = cost_of_equity(risk_free_rate=0.045, beta=1.0, equity_risk_premium=0.1394)
    assert result == pytest.approx(0.1844)


def test_wacc_all_equity_equals_cost_of_equity():
    result = wacc(cost_of_equity_=0.18, cost_of_debt=0.08, tax_rate=0.25, weight_equity=1.0, weight_debt=0.0)
    assert result == pytest.approx(0.18)


def test_wacc_with_debt_lowers_result():
    all_equity = wacc(0.18, 0.08, 0.25, weight_equity=1.0, weight_debt=0.0)
    with_debt = wacc(0.18, 0.08, 0.25, weight_equity=0.7, weight_debt=0.3)
    assert with_debt < all_equity  # debt is cheaper than equity here