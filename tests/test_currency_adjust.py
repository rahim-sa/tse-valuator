import pytest

from tse_valuator.valuation.currency_adjust import convert_rial_to_usd, deflate_to_real

# Real CPI values fetched live from World Bank FP.CPI.TOTL (2010=100)
REAL_IRAN_CPI = {
    2023: 2140.21942916994,
    2024: 2834.84629484158,
    2025: 4030.3356899712,
}

# Real شپدیس consolidated revenue, million rial (from tests/fixtures)
REVENUE_1402 = 347_856_284  # fiscal year ending ~Sept 2023
REVENUE_1403 = 424_017_802  # fiscal year ending ~Sept 2024
REVENUE_1404 = 600_474_556  # fiscal year ending ~Sept 2025


def test_deflate_missing_year_raises():
    with pytest.raises(KeyError):
        deflate_to_real(100, from_year=2019, to_base_year=2023, cpi_series=REAL_IRAN_CPI)


def test_same_year_deflation_is_identity():
    result = deflate_to_real(REVENUE_1402, from_year=2023, to_base_year=2023, cpi_series=REAL_IRAN_CPI)
    assert result == pytest.approx(REVENUE_1402)


def test_real_revenue_actually_declined_despite_nominal_growth():
    """
    This is the core finding this whole currency-adjustment module
    exists for: شپدیس's revenue grew ~73% in NOMINAL rial terms from
    1402->1404, but once CPI-deflated to constant 2023 purchasing
    power, real revenue actually DECLINED. Nominal growth here is
    substantially a currency/inflation artifact, not real business
    growth -- exactly the distortion a naive DCF would miss.
    """
    real_1404 = deflate_to_real(
        REVENUE_1404, from_year=2025, to_base_year=2023, cpi_series=REAL_IRAN_CPI
    )
    nominal_growth = (REVENUE_1404 / REVENUE_1402) - 1
    real_growth = (real_1404 / REVENUE_1402) - 1

    assert nominal_growth > 0.70  # ~73% nominal growth
    assert real_growth < 0  # but real terms: a decline
    assert real_1404 == pytest.approx(318_876_000, rel=0.01)


def test_convert_rial_to_usd_basic():
    # Real rate we verified live: 1404/06/31 -> 1,033,000 rial/USD
    usd_value = convert_rial_to_usd(1_033_000, usd_irr_rate=1_033_000)
    assert usd_value == pytest.approx(1.0)


def test_convert_rial_to_usd_rejects_non_positive_rate():
    with pytest.raises(ValueError):
        convert_rial_to_usd(1000, usd_irr_rate=0)

def test_deflate_handles_decreasing_cpi_correctly():
    # Deflation (CPI falling between years) is rare but our function
    # shouldn't assume inflation only moves one direction -- the math
    # (a ratio) is direction-agnostic by construction, confirm it holds.
    cpi_series = {2020: 120.0, 2021: 100.0}  # CPI fell
    result = deflate_to_real(1000, from_year=2020, to_base_year=2021, cpi_series=cpi_series)
    expected = 1000 * (100.0 / 120.0)
    assert result == pytest.approx(expected)
    assert result < 1000  # value should shrink since base-year prices were lower