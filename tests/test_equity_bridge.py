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