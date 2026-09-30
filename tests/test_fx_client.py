import pytest

from tse_valuator.macro.fx_client import FxDataUnavailableError, get_usd_irr_rate


def test_known_date_returns_expected_rate():
    # Verified directly: 1404/06/31 -> usd sell 103300 Toman -> 1,033,000 Rial
    rate = get_usd_irr_rate("1404/06/31")
    assert rate == 1_033_000


def test_buy_vs_sell_rate_differ():
    sell = get_usd_irr_rate("1404/06/31", rate_type="sell")
    buy = get_usd_irr_rate("1404/06/31", rate_type="buy")
    assert sell != buy
    assert buy < sell  # sell is always >= buy in FX quoting convention