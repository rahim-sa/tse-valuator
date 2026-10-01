import pytest


from tse_valuator.macro.fx_client import FxDataUnavailableError, get_usd_irr_rate, get_average_usd_irr_rate


def test_known_date_returns_expected_rate():
    # Verified directly: 1404/06/31 -> usd sell 103300 Toman -> 1,033,000 Rial
    rate = get_usd_irr_rate("1404/06/31")
    assert rate == 1_033_000


def test_buy_vs_sell_rate_differ():
    sell = get_usd_irr_rate("1404/06/31", rate_type="sell")
    buy = get_usd_irr_rate("1404/06/31", rate_type="buy")
    assert sell != buy
    assert buy < sell  # sell is always >= buy in FX quoting convention

def test_average_rate_is_between_min_and_max_of_period():
    # شپدیس fiscal year 1404: roughly 1403/07/01 to 1404/06/31
    avg = get_average_usd_irr_rate("1404/06/01", "1404/06/31")  # just the last month, cheap test
    single_day_start = get_usd_irr_rate("1404/06/01")
    single_day_end = get_usd_irr_rate("1404/06/31")
    low = min(single_day_start, single_day_end)
    high = max(single_day_start, single_day_end)
    assert low <= avg <= high