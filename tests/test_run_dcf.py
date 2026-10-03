from datetime import date

from tse_valuator.valuation.run_dcf import run_dcf_valuation, DcfAssumptions


def test_shapadis_full_pipeline_runs_and_produces_sane_result():
    result = run_dcf_valuation(
        symbol="شپدیس",
        fiscal_year_jalali=1404, fiscal_month=6, fiscal_day=31,
        fiscal_gregorian_date=date(2025, 9, 22),
        prior_fiscal_year_jalali=1403,
        prior_fiscal_gregorian_date=date(2024, 9, 21),
    )
    assert result.value_per_share_rial > 0
    assert result.market_price_rial > 0
    assert result.wacc > result.terminal_growth_rate if hasattr(result, "terminal_growth_rate") else True
    assert -90 < result.gap_vs_market_pct < 500  # sane bounds, not a tight assertion
    print(result)