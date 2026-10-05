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

def test_wacc_realistic_mixed_capital_structure():
    # A company financed 60% equity / 40% debt -- a realistic, nonzero
    # leverage case, which none of our real company tests have hit yet
    # (شپدیس, خصدرا, and بترانس all happened to carry ~0% interest-bearing debt).
    ce = cost_of_equity(risk_free_rate=0.045, beta=1.2, equity_risk_premium=0.1394)
    result = wacc(ce, cost_of_debt=0.09, tax_rate=0.25, weight_equity=0.6, weight_debt=0.4)
    expected = 0.6 * ce + 0.4 * 0.09 * (1 - 0.25)
    assert result == pytest.approx(expected)


def test_wacc_decreases_monotonically_as_debt_weight_increases_when_debt_cheaper():
    ce = 0.18
    cost_of_debt = 0.08  # cheaper than equity, after-tax even more so
    tax_rate = 0.25
    results = [
        wacc(ce, cost_of_debt, tax_rate, weight_equity=1 - d, weight_debt=d)
        for d in [0.0, 0.2, 0.4, 0.6, 0.8]
    ]
    assert results == sorted(results, reverse=True)  # strictly decreasing as debt weight rises