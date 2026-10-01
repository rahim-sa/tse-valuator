import pytest
from tse_valuator.valuation.dcf import enterprise_value, present_value, project_fcf, terminal_value


def test_project_fcf_compounds_correctly():
    result = project_fcf(100, [0.1, 0.1, 0.05])
    assert result[0] == pytest.approx(110)
    assert result[1] == pytest.approx(121)
    assert result[2] == pytest.approx(127.05)


def test_terminal_value_raises_if_rate_too_low():
    with pytest.raises(ValueError):
        terminal_value(100, terminal_growth_rate=0.10, discount_rate=0.08)


def test_present_value_basic():
    result = present_value([100, 100], discount_rate=0.10)
    assert result == pytest.approx(100 / 1.10 + 100 / 1.10**2)


def test_enterprise_value_breakdown_has_all_components():
    result = enterprise_value(
        base_fcf=1000, growth_rates=[0.1, 0.08, 0.05], terminal_growth_rate=0.03, discount_rate=0.15
    )
    assert "enterprise_value" in result
    assert result["enterprise_value"] > result["pv_explicit_period"]
    assert result["enterprise_value"] == pytest.approx(
        result["pv_explicit_period"] + result["pv_terminal_value"]
    )