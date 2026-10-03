from tse_valuator.macro.cpi_client import CpiDataUnavailableError, get_cpi_for_year
import pytest


def test_get_cpi_for_year_raises_on_missing_year():
    with pytest.raises(CpiDataUnavailableError):
        get_cpi_for_year({2020: 150.0, 2021: 180.0}, 2019)


def test_get_cpi_for_year_returns_known_value():
    series = {2020: 150.0, 2021: 180.0}
    assert get_cpi_for_year(series, 2021) == 180.0

from tse_valuator.macro.cpi_client import fetch_iran_cpi_annual


def test_fetch_iran_cpi_annual_returns_real_accelerating_series():
    cpi = fetch_iran_cpi_annual(start_year=2015, end_year=2023)
    assert 2015 in cpi
    assert 2020 in cpi
    # Confirmed hyperinflation pattern: each multi-year span shows
    # meaningfully accelerating growth, not flat or erratic data.
    assert cpi[2020] > cpi[2015] * 2  # roughly doubled 2015->2020
    assert cpi[2023] > cpi[2020] * 2  # roughly doubled again 2020->2023