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

def test_enterprise_value_with_single_year_projection():
    # Shortest possible explicit period -- just one year before terminal value
    result = enterprise_value(
        base_fcf=1000, growth_rates=[0.05], terminal_growth_rate=0.02, discount_rate=0.15
    )
    assert len(result["projected_fcf"]) == 1
    assert result["projected_fcf"][0] == pytest.approx(1050)
    assert result["enterprise_value"] > 0


def test_enterprise_value_with_zero_growth_throughout():
    # A flat, no-growth company -- base_fcf never changes year to year
    result = enterprise_value(
        base_fcf=1000, growth_rates=[0.0, 0.0, 0.0], terminal_growth_rate=0.0, discount_rate=0.15
    )
    assert all(fcf == pytest.approx(1000) for fcf in result["projected_fcf"])
    # With 0% terminal growth, terminal value should equal FCF / discount_rate (perpetuity, no growth)
    expected_tv = 1000 / 0.15
    assert result["terminal_value_undiscounted"] == pytest.approx(expected_tv)


def test_enterprise_value_terminal_value_dominates_for_long_low_discount_scenarios():
    # Sanity check: with a low discount rate close to terminal growth,
    # terminal value should be a LARGE share of total enterprise value
    # (a well-known DCF sensitivity, worth having as a regression anchor)
    result = enterprise_value(
        base_fcf=1000, growth_rates=[0.03, 0.03, 0.03], terminal_growth_rate=0.025, discount_rate=0.06
    )
    terminal_share = result["pv_terminal_value"] / result["enterprise_value"]
    assert terminal_share > 0.7  # terminal value should dominate in this low-spread scenario