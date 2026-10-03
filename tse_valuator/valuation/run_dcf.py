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
from tse_valuator.macro.fx_client import get_usd_irr_rate, get_average_usd_irr_rate
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
    """Raised when fewer than 2 annual filings are found -- unlevered_fcf
    needs a prior-year NWC figure, so a single year isn't enough."""
    def __init__(self, symbol: str, found: int):
        self.symbol = symbol
        super().__init__(f"Need at least 2 annual consolidated filings for {symbol}, found {found}")


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


def run_dcf_valuation(
    symbol: str,
    fiscal_year_jalali: int,
    fiscal_month: int,
    fiscal_day: int,
    fiscal_gregorian_date: date,
    prior_fiscal_year_jalali: int,
    prior_fiscal_gregorian_date: date,
    assumptions: DcfAssumptions | None = None,
) -> DcfValuationResult:
    """
    Runs a complete DCF valuation for a TSE symbol, using live Codal
    financial data, live FX/CPI/country-risk data, and live TSETMC
    market data. Fiscal period dates must be supplied explicitly (not
    auto-detected) since filing title parsing is not yet automated --
    see scratch-script history for why this is deliberately manual for now.
    """
    assumptions = assumptions or DcfAssumptions()

    filings = search_filings(symbol, from_jdate="1401/01/01")
    annual = [
        f for f in filings
        if "سال مالی" in f.title and "میاندوره" not in f.title
        and "شرکت" not in f.title and "حسابرسی نشده" not in f.title
        and "تلفیقی" in f.title
    ]
    annual_sorted = sorted(annual, key=lambda f: f.title, reverse=True)

    if len(annual_sorted) < 2:
        raise InsufficientFilingDataError(symbol, len(annual_sorted))

    stmt_current = _fetch_statement(
        annual_sorted[0], fiscal_year_jalali, fiscal_month, fiscal_day, fiscal_gregorian_date, symbol
    )
    stmt_prior = _fetch_statement(
        annual_sorted[1], prior_fiscal_year_jalali, fiscal_month, fiscal_day, prior_fiscal_gregorian_date, symbol
    )

    fcf_current = extract_fcf_inputs(stmt_current, tax_rate=assumptions.tax_rate)
    fcf_prior = extract_fcf_inputs(stmt_prior, tax_rate=assumptions.tax_rate)
    base_fcf_rial_millions = unlevered_fcf(fcf_current, prior_nwc=fcf_prior.net_working_capital)

    fiscal_start = f"{prior_fiscal_year_jalali}/{(fiscal_month % 12) + 1:02d}/01"
    fiscal_end = f"{fiscal_year_jalali}/{fiscal_month:02d}/{fiscal_day:02d}"
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