"""
End-to-end DCF orchestration: ties together ingestion, macro data, and
valuation math into one callable pipeline for a given TSE symbol.

This module coordinates; it does not itself compute anything novel --
every number here comes from the already-tested modules in
ingestion/, macro/, and valuation/. See those modules for the actual
formulas and data-sourcing logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import jdatetime

from tse_valuator.ingestion.codal_client import search_filings, download_filing_excel
from tse_valuator.ingestion.schema import (
    ConsolidationBasis, FiscalPeriod, LineItemKey, PeriodType, StatementType, NormalizedStatement,
)
from tse_valuator.ingestion.statement_builder import build_normalized_statement
from tse_valuator.valuation.free_cash_flow import extract_fcf_inputs, unlevered_fcf
from tse_valuator.valuation.wacc import cost_of_equity, wacc
from tse_valuator.valuation.dcf import enterprise_value
from tse_valuator.valuation.equity_bridge import equity_value, value_per_share
from tse_valuator.valuation.currency_adjust import deflate_to_real
from tse_valuator.macro.fx_client import get_usd_irr_rate, get_average_usd_irr_rate
from tse_valuator.macro.cpi_client import fetch_iran_cpi_annual
from tse_valuator.macro.country_risk_client import fetch_country_risk_premium
from tse_valuator.macro.tsetmc_client import get_current_market_data


@dataclass
class DcfAssumptions:
    """Explicit, analyst-supplied assumptions -- see wacc.py and
    country_risk_client.py docstrings for why these are inputs, not
    fetched/fitted automatically."""
    tax_rate: float = 0.25
    risk_free_rate: float = 0.045
    beta: float = 1.0
    cost_of_debt: float = 0.09
    growth_rates: list[float] = field(default_factory=lambda: [0.04, 0.035, 0.03, 0.03, 0.025])
    terminal_growth_rate: float = 0.02


@dataclass
class DcfValuationResult:
    symbol: str
    base_fcf_rial_millions: float
    base_fcf_usd: float
    fcf_years_used: list[int]
    avg_fx_rate: float
    period_end_fx_rate: float
    fx_rate_today: float
    cost_of_equity: float
    wacc: float
    debt_weight: float
    enterprise_value_usd: float
    equity_value_usd: float
    shares_outstanding: float
    value_per_share_usd: float
    value_per_share_rial: float
    market_price_rial: float
    market_price_date: str
    gap_vs_market_pct: float


class InsufficientFilingDataError(Exception):
    """Raised when fewer annual filings are found than needed.
    Computing N years of FCF requires N+1 statements (each FCF needs
    the PRIOR year's net working capital)."""
    def __init__(self, symbol: str, found: int, needed: int):
        self.symbol = symbol
        super().__init__(f"Need at least {needed} annual consolidated filings for {symbol}, found {found}")


def _fetch_statement(filing, jy: int, jm: int, jd: int, gdate: date, symbol: str) -> NormalizedStatement:
    html_bytes = download_filing_excel(filing.excel_url)
    period = FiscalPeriod(
        period_type=PeriodType.ANNUAL, jalali_year=jy,
        jalali_end_date=f"{jy}/{jm:02d}/{jd:02d}", gregorian_end_date=gdate,
    )
    result = build_normalized_statement(
        html_bytes=html_bytes, filing_url=filing.excel_url, symbol_fa=symbol,
        company_name_fa=filing.company_name, statement_type=StatementType.INCOME_STATEMENT,
        consolidation_basis=ConsolidationBasis.CONSOLIDATED, period=period,
    )
    return result.statement


def _build_cpi_series_with_extrapolation(years_needed: list[int]) -> dict[int, float]:
    """
    Fetches the live CPI series and extrapolates forward for any
    requested year not yet published (World Bank data has a publication
    lag). Extrapolation uses the latest known annual inflation rate --
    freezing at the last known value would wrongly imply 0% inflation
    for the gap.
    """
    cpi_series = fetch_iran_cpi_annual(start_year=2015, end_year=2027)
    latest_available_year = max(cpi_series.keys())
    second_latest_year = latest_available_year - 1

    if second_latest_year not in cpi_series:
        raise ValueError("Need at least 2 years of CPI data to extrapolate a missing year")

    latest_known_inflation = cpi_series[latest_available_year] / cpi_series[second_latest_year] - 1

    def _cpi_for_year(year: int) -> float:
        if year in cpi_series:
            return cpi_series[year]
        years_ahead = year - latest_available_year
        return cpi_series[latest_available_year] * (1 + latest_known_inflation) ** years_ahead

    extended = dict(cpi_series)
    for y in years_needed:
        if y not in extended:
            extended[y] = _cpi_for_year(y)
            print(f"[note] CPI for {y} not yet published; extrapolated using {latest_known_inflation:.1%} latest known inflation rate")

    return extended


def _approx_gregorian(base_gregorian: date, year_offset: int) -> date:
    """Approximates a Gregorian date N years before/after a given one,
    for the purpose of CPI year lookups -- exact day precision doesn't
    matter here, only the calendar year."""
    try:
        return base_gregorian.replace(year=base_gregorian.year + year_offset)
    except ValueError:
        return base_gregorian.replace(year=base_gregorian.year + year_offset, day=28)


def run_dcf_valuation(
    symbol: str,
    fiscal_year_jalali: int,
    fiscal_month: int,
    fiscal_day: int,
    fiscal_gregorian_date: date,
    prior_fiscal_year_jalali: int,
    prior_fiscal_gregorian_date: date,
    assumptions: DcfAssumptions | None = None,
    num_base_fcf_years: int = 1,
) -> DcfValuationResult:
    """
    Runs a complete DCF valuation for a TSE symbol, using live Codal
    financial data, live FX/CPI/country-risk data, and live TSETMC
    market data.

    num_base_fcf_years: how many years of real (CPI-deflated) FCF to
    average as the DCF's base year, instead of using a single year.
    Default 1 preserves prior behavior. Averaging guards against a
    single unusual year (e.g. a one-off working-capital swing)
    dominating the entire multi-year projection.
    """
    assumptions = assumptions or DcfAssumptions()
    num_statements_needed = num_base_fcf_years + 1

    filings = search_filings(symbol, from_jdate="1399/01/01")
    annual = [
        f for f in filings
        if "سال مالی" in f.title and "میاندوره" not in f.title
        and "شرکت" not in f.title and "حسابرسی نشده" not in f.title
        and "تلفیقی" in f.title
    ]
    annual_sorted = sorted(annual, key=lambda f: f.title, reverse=True)

    if len(annual_sorted) < num_statements_needed:
        raise InsufficientFilingDataError(symbol, len(annual_sorted), num_statements_needed)

    statements = []
    for i in range(num_statements_needed):
        jy = fiscal_year_jalali - i
        gdate = _approx_gregorian(fiscal_gregorian_date, -i)
        stmt = _fetch_statement(annual_sorted[i], jy, fiscal_month, fiscal_day, gdate, symbol)
        statements.append((jy, gdate, stmt))

    years_needed = [gdate.year for _, gdate, _ in statements]
    cpi_series = _build_cpi_series_with_extrapolation(years_needed)
    base_year = statements[0][1].year

    real_fcf_values = []
    for i in range(num_base_fcf_years):
        jy_current, gdate_current, stmt_current = statements[i]
        jy_prior, gdate_prior, stmt_prior = statements[i + 1]

        fcf_current = extract_fcf_inputs(stmt_current, tax_rate=assumptions.tax_rate)
        fcf_prior = extract_fcf_inputs(stmt_prior, tax_rate=assumptions.tax_rate)

        real_nwc_current = deflate_to_real(
            fcf_current.net_working_capital, from_year=gdate_current.year, to_base_year=base_year, cpi_series=cpi_series
        )
        real_nwc_prior = deflate_to_real(
            fcf_prior.net_working_capital, from_year=gdate_prior.year, to_base_year=base_year, cpi_series=cpi_series
        )
        fcf_current.net_working_capital = real_nwc_current
        nominal_fcf = unlevered_fcf(fcf_current, prior_nwc=real_nwc_prior)

        real_fcf = deflate_to_real(nominal_fcf, from_year=gdate_current.year, to_base_year=base_year, cpi_series=cpi_series)
        real_fcf_values.append((jy_current, real_fcf))

    base_fcf_rial_millions = sum(v for _, v in real_fcf_values) / len(real_fcf_values)
    fcf_years_used = [jy for jy, _ in real_fcf_values]

    stmt_current = statements[0][2]
    fiscal_end = f"{fiscal_year_jalali}/{fiscal_month:02d}/{fiscal_day:02d}"
    fiscal_start = f"{prior_fiscal_year_jalali}/{(fiscal_month % 12) + 1:02d}/01"
    avg_fx_rate = get_average_usd_irr_rate(fiscal_start, fiscal_end)
    period_end_fx_rate = get_usd_irr_rate(fiscal_end)
    today_jalali = jdatetime.date.today().strftime("%Y/%m/%d")
    fx_rate_today = get_usd_irr_rate(today_jalali)

    base_fcf_usd = (base_fcf_rial_millions * 1_000_000) / avg_fx_rate

    crp_data = fetch_country_risk_premium("Iran")
    erp = crp_data["Final ERP"]
    re = cost_of_equity(assumptions.risk_free_rate, assumptions.beta, erp)

    total_equity = stmt_current.get(LineItemKey.TOTAL_EQUITY).value_rial
    bank_debt_item = stmt_current.get(LineItemKey.BANK_BORROWINGS)
    interest_bearing_debt = bank_debt_item.value_rial if bank_debt_item else 0
    cash_rial = stmt_current.get(LineItemKey.CASH_AND_EQUIVALENTS).value_rial

    total_capital = total_equity + interest_bearing_debt
    w_equity = total_equity / total_capital
    w_debt = interest_bearing_debt / total_capital

    discount_rate = wacc(re, assumptions.cost_of_debt, assumptions.tax_rate, w_equity, w_debt)

    dcf_result = enterprise_value(
        base_fcf_usd, assumptions.growth_rates, assumptions.terminal_growth_rate, discount_rate
    )

    total_debt_usd = (interest_bearing_debt * 1_000_000) / period_end_fx_rate
    cash_usd = (cash_rial * 1_000_000) / period_end_fx_rate
    eq_value_usd = equity_value(dcf_result["enterprise_value"], total_debt_usd, cash_usd)

    market_data = get_current_market_data(symbol)
    per_share_usd = value_per_share(eq_value_usd, market_data["shares_outstanding"])
    per_share_rial = per_share_usd * fx_rate_today

    gap_pct = (per_share_rial / market_data["latest_close_rial"] - 1) * 100

    return DcfValuationResult(
        symbol=symbol,
        base_fcf_rial_millions=base_fcf_rial_millions,
        base_fcf_usd=base_fcf_usd,
        fcf_years_used=fcf_years_used,
        avg_fx_rate=avg_fx_rate,
        period_end_fx_rate=period_end_fx_rate,
        fx_rate_today=fx_rate_today,
        cost_of_equity=re,
        wacc=discount_rate,
        debt_weight=w_debt,
        enterprise_value_usd=dcf_result["enterprise_value"],
        equity_value_usd=eq_value_usd,
        shares_outstanding=market_data["shares_outstanding"],
        value_per_share_usd=per_share_usd,
        value_per_share_rial=per_share_rial,
        market_price_rial=market_data["latest_close_rial"],
        market_price_date=str(market_data["latest_date"]),
        gap_vs_market_pct=gap_pct,
    )