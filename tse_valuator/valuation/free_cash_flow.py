"""
Computes unlevered free cash flow (FCF) from NormalizedStatement data.

FCF = EBIT * (1 - tax_rate) + D&A - CapEx - Change in Net Working Capital

All inputs here should already be in REAL terms (CPI-deflated) before
being passed to this module -- see currency_adjust.py. This module
does not itself apply any inflation adjustment; mixing that concern in
here would make it harder to test and audit independently.

Net working capital = (receivables + inventory) - payables. This is a
simplification -- a fuller model might include other current
operating assets/liabilities -- but it's a defensible, common
approximation and is explicit about what it includes.
"""

from __future__ import annotations

from dataclasses import dataclass

from tse_valuator.ingestion.schema import LineItemKey, NormalizedStatement


class MissingLineItemError(Exception):
    """Raised when a required line item is absent (or genuinely missing
    in the filing) -- we do not silently treat it as zero, since a
    missing revenue or EBIT number is a very different situation from
    a genuine zero."""

    def __init__(self, key: LineItemKey, symbol: str, year: int):
        self.key = key
        super().__init__(f"Missing required line item {key.value} for {symbol} year {year}")


@dataclass
class FcfInputs:
    """One period's inputs to the FCF calculation, already resolved to
    plain numbers -- keeps free_cash_flow() itself simple and testable
    without needing full NormalizedStatement objects in every test."""
    operating_income: float  # EBIT (our OPERATING_INCOME key)
    tax_rate: float          # as a decimal, e.g. 0.25 for 25%
    depreciation_amortization: float
    capex: float
    net_working_capital: float  # NOT the change -- the level, for this period


def net_working_capital(receivables: float, inventory: float, payables: float) -> float:
    return (receivables + inventory) - payables


def unlevered_fcf(current: FcfInputs, prior_nwc: float) -> float:
    """
    Computes one period's unlevered FCF, given this period's inputs and
    the PRIOR period's net working capital level (needed to compute
    the change). capex is expected as a positive number representing
    cash outflow (our schema already stores it this way -- verify sign
    convention against real data before trusting this blindly).
    """
    nopat = current.operating_income * (1 - current.tax_rate)
    change_in_nwc = current.net_working_capital - prior_nwc
    return nopat + current.depreciation_amortization - current.capex - change_in_nwc


def extract_fcf_inputs(statement: NormalizedStatement, tax_rate: float) -> FcfInputs:
    """
    Pulls required line items from a NormalizedStatement, raising
    MissingLineItemError immediately if anything essential is absent
    -- never substituting zero for a missing value.
    """
    required = {
        LineItemKey.OPERATING_INCOME: "operating_income",
        LineItemKey.DEPRECIATION_AMORTIZATION: "depreciation_amortization",
        LineItemKey.CAPEX: "capex",
        LineItemKey.TRADE_RECEIVABLES: "receivables",
        LineItemKey.INVENTORY: "inventory",
        LineItemKey.TRADE_PAYABLES: "payables",
    }
    values = {}
    for key, _ in required.items():
        item = statement.get(key)
        if item is None or item.value_rial is None:
            raise MissingLineItemError(key, statement.symbol_fa, statement.period.jalali_year)
        values[key] = item.value_rial

    nwc = net_working_capital(
        receivables=values[LineItemKey.TRADE_RECEIVABLES],
        inventory=values[LineItemKey.INVENTORY],
        payables=values[LineItemKey.TRADE_PAYABLES],
    )

        
    # Codal's cash flow statement records capex as a cash OUTFLOW, shown
    # with parentheses in the source filing, which value_parser.py
    # correctly preserves as a negative number. unlevered_fcf() expects
    # capex as a positive magnitude (it subtracts it explicitly), so we
    # normalize the sign here -- confirmed against a real شپدیس filing,
    # where raw capex was -2,693,532 (a genuine outflow).
    return FcfInputs(
        operating_income=values[LineItemKey.OPERATING_INCOME],
        tax_rate=tax_rate,
        depreciation_amortization=values[LineItemKey.DEPRECIATION_AMORTIZATION],
        capex=abs(values[LineItemKey.CAPEX]),
        net_working_capital=nwc,
    )