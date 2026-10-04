import pytest
from tse_valuator.valuation.equity_bridge import equity_value, value_per_share


def test_equity_value_subtracts_debt_adds_cash():
    result = equity_value(enterprise_value_=1000, total_debt=300, cash_and_equivalents=50)
    assert result == 750


def test_value_per_share_basic():
    assert value_per_share(1000, 100) == 10


def test_value_per_share_rejects_zero_shares():
    with pytest.raises(ValueError):
        value_per_share(1000, 0)

def test_equity_value_handles_negative_enterprise_value_without_crashing():
    # Confirmed real scenario: خصدرا and بترانس both produced negative
    # enterprise values before the CPI/NWC fix. The function should
    # still compute cleanly (even if the economic interpretation is
    # "something is wrong upstream") rather than raising.
    result = equity_value(enterprise_value_=-1000, total_debt=200, cash_and_equivalents=50)
    assert result == -1150  # -1000 - 200 + 50, arithmetic holds regardless of sign


def test_value_per_share_with_negative_equity_value():
    # Should still compute (producing a negative per-share value) --
    # the function's job is arithmetic, not judging economic plausibility.
    # A negative result is a signal to the CALLER to investigate upstream
    # assumptions, not something this function should silently guard against.
    result = value_per_share(-500, 100)
    assert result == -5.0