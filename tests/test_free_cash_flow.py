import pytest

from tse_valuator.valuation.free_cash_flow import (
    FcfInputs,
    net_working_capital,
    unlevered_fcf,
)


def test_net_working_capital_basic():
    assert net_working_capital(receivables=100, inventory=50, payables=30) == 120


def test_unlevered_fcf_with_no_nwc_change():
    inputs = FcfInputs(
        operating_income=1000,
        tax_rate=0.25,
        depreciation_amortization=200,
        capex=150,
        net_working_capital=500,
    )
    # NOPAT = 1000 * 0.75 = 750; +200 D&A; -150 capex; -0 NWC change = 800
    result = unlevered_fcf(inputs, prior_nwc=500)
    assert result == pytest.approx(800)


def test_unlevered_fcf_with_increasing_nwc_reduces_fcf():
    inputs = FcfInputs(
        operating_income=1000,
        tax_rate=0.25,
        depreciation_amortization=200,
        capex=150,
        net_working_capital=600,  # up from 500 -- NWC grew, consuming cash
    )
    result = unlevered_fcf(inputs, prior_nwc=500)
    # Same as above but with an extra 100 NWC increase subtracted
    assert result == pytest.approx(700)


def test_unlevered_fcf_with_decreasing_nwc_increases_fcf():
    inputs = FcfInputs(
        operating_income=1000,
        tax_rate=0.25,
        depreciation_amortization=200,
        capex=150,
        net_working_capital=400,  # down from 500 -- NWC released cash
    )
    result = unlevered_fcf(inputs, prior_nwc=500)
    assert result == pytest.approx(900)


from datetime import date
from pathlib import Path

from tse_valuator.ingestion.schema import (
    ConsolidationBasis, FiscalPeriod, PeriodType, StatementType,
)
from tse_valuator.ingestion.statement_builder import build_normalized_statement
from tse_valuator.valuation.free_cash_flow import extract_fcf_inputs

FIXTURE = Path(__file__).parent / "fixtures" / "shapadis_annual_1404.xlsx"


def test_extract_fcf_inputs_normalizes_capex_to_positive():
    """
    Regression test for a real bug: Codal stores capex as a NEGATIVE
    cash outflow (parenthesized in source), but unlevered_fcf() expects
    a positive magnitude. Confirmed against a real شپدیس filing where
    raw capex was -2,693,532.
    """
    html_bytes = FIXTURE.read_bytes()
    period = FiscalPeriod(
        period_type=PeriodType.ANNUAL,
        jalali_year=1404,
        jalali_end_date="1404/06/31",
        gregorian_end_date=date(2025, 9, 22),
    )
    result = build_normalized_statement(
        html_bytes=html_bytes,
        filing_url="https://excel.codal.ir/service/Excel/GetAll/GVzCYzVxWC1QdFQldBkovg%3d%3d/0",
        symbol_fa="شپدیس",
        company_name_fa="پترو شیمی پردیس",
        statement_type=StatementType.INCOME_STATEMENT,
        consolidation_basis=ConsolidationBasis.CONSOLIDATED,
        period=period,
    )
    fcf_inputs = extract_fcf_inputs(result.statement, tax_rate=0.25)
    assert fcf_inputs.capex > 0
    assert fcf_inputs.capex == pytest.approx(2_693_532)


def test_extract_fcf_inputs_treats_missing_da_as_zero_not_error():
    """
    Regression test: an asset-light company (e.g. خصدرا, a contracting
    company) may have no D&A line at all -- this is a legitimate
    business characteristic, not missing data, and must default to 0
    rather than raise an error.
    """
    from tse_valuator.ingestion.codal_client import search_filings, download_filing_excel
    from tse_valuator.ingestion.statement_builder import build_normalized_statement
    from tse_valuator.ingestion.schema import ConsolidationBasis, FiscalPeriod, PeriodType, StatementType
    from datetime import date

    filings = search_filings("خصدرا", from_jdate="1404/01/01")
    target = next(
        f for f in filings
        if "۱۴۰۴/۱۲/۲۹" in f.title and "حسابرسی شده" in f.title and "نشده" not in f.title
    )
    html_bytes = download_filing_excel(target.excel_url)
    period = FiscalPeriod(
        period_type=PeriodType.ANNUAL, jalali_year=1404,
        jalali_end_date="1404/12/29", gregorian_end_date=date(2026, 3, 20),
    )
    result = build_normalized_statement(
        html_bytes=html_bytes, filing_url=target.excel_url, symbol_fa="خصدرا",
        company_name_fa=target.company_name, statement_type=StatementType.INCOME_STATEMENT,
        consolidation_basis=ConsolidationBasis.CONSOLIDATED, period=period,
    )
    fcf_inputs = extract_fcf_inputs(result.statement, tax_rate=0.25)
    assert fcf_inputs.depreciation_amortization == 0.0