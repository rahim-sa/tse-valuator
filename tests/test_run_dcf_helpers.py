from datetime import date

import pytest

from tse_valuator.valuation.run_dcf import _approx_gregorian, _build_cpi_series_with_extrapolation


def test_approx_gregorian_one_year_back():
    result = _approx_gregorian(date(2025, 9, 22), -1)
    assert result == date(2024, 9, 22)


def test_approx_gregorian_two_years_forward():
    result = _approx_gregorian(date(2024, 3, 20), 2)
    assert result == date(2026, 3, 20)


def test_approx_gregorian_handles_leap_day():
    # Feb 29 doesn't exist in a non-leap year -- must not crash
    result = _approx_gregorian(date(2024, 2, 29), 1)  # 2025 is not a leap year
    assert result == date(2025, 2, 28)


def test_cpi_extrapolation_uses_latest_known_inflation_rate():
    # Simulate fetch_iran_cpi_annual returning a known series by
    # monkeypatching -- isolates this function from the live API entirely
    import tse_valuator.valuation.run_dcf as run_dcf_module

    def fake_fetch(start_year, end_year):
        return {2022: 100.0, 2023: 150.0, 2024: 200.0}  # known 33.3% growth 2023->2024

    original = run_dcf_module.fetch_iran_cpi_annual
    run_dcf_module.fetch_iran_cpi_annual = fake_fetch
    try:
        result = _build_cpi_series_with_extrapolation([2025])
        expected_inflation = 200.0 / 150.0 - 1
        expected_2025 = 200.0 * (1 + expected_inflation)
        assert result[2025] == pytest.approx(expected_2025)
        assert result[2022] == 100.0  # untouched known years stay as-is
        assert result[2024] == 200.0
    finally:
        run_dcf_module.fetch_iran_cpi_annual = original


def test_cpi_extrapolation_does_not_touch_already_known_years():
    import tse_valuator.valuation.run_dcf as run_dcf_module

    def fake_fetch(start_year, end_year):
        return {2022: 100.0, 2023: 150.0}

    original = run_dcf_module.fetch_iran_cpi_annual
    run_dcf_module.fetch_iran_cpi_annual = fake_fetch
    try:
        result = _build_cpi_series_with_extrapolation([2023])  # already known
        assert result[2023] == 150.0
    finally:
        run_dcf_module.fetch_iran_cpi_annual = original


def test_cpi_extrapolation_raises_with_insufficient_history():
    import tse_valuator.valuation.run_dcf as run_dcf_module

    def fake_fetch(start_year, end_year):
        return {2024: 200.0}  # only one year -- can't compute an inflation rate

    original = run_dcf_module.fetch_iran_cpi_annual
    run_dcf_module.fetch_iran_cpi_annual = fake_fetch
    try:
        with pytest.raises(ValueError):
            _build_cpi_series_with_extrapolation([2025])
    finally:
        run_dcf_module.fetch_iran_cpi_annual = original