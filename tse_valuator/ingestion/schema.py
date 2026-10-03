# SCOPE: this schema targets non-financial companies (industrials,
# materials, consumer, etc.). Banks, insurers, and other financial
# institutions have fundamentally different statement structures
# (loans/deposits as core business, not financing; loan-loss
# provisions; no "cost of revenue" concept) and are NOT supported --
# confirmed by testing against a real Bank Mellat filing, which mapped
# only 7/416 labels. Financial institutions would need their own
# schema and likely a different valuation methodology entirely
# (dividend discount / excess-return / P-B multiples rather than
# unlevered FCFF DCF). Out of scope for now; revisit deliberately if
# needed later.


"""
Normalized financial statement schema.

This is the hard boundary in the pipeline: the LLM extraction step must
produce data conforming to this schema, and everything downstream (DCF,
comps) only ever reads from validated instances of it — never from raw
LLM text and never by letting the LLM compute a derived number itself.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl, field_validator


class StatementType(str, Enum):
    INCOME_STATEMENT = "income_statement"
    BALANCE_SHEET = "balance_sheet"
    CASH_FLOW = "cash_flow"


class ConsolidationBasis(str, Enum):
    CONSOLIDATED = "consolidated"       # تلفیقی
    STANDALONE = "standalone"            # اصلی / شرکت اصلی


class PeriodType(str, Enum):
    ANNUAL = "annual"
    QUARTERLY = "quarterly"
    SIX_MONTH = "six_month"
    NINE_MONTH = "nine_month"


class LineItemKey(str, Enum):
    """
    Canonical taxonomy. This is our stand-in for an XBRL taxonomy --
    since Codal has none, WE define the controlled vocabulary that every
    extracted line item must map into. Extended based on real coverage
    testing against شپدیس (petrochemicals) and فولاد (steel) filings.
    """
    REVENUE = "revenue"
    COST_OF_REVENUE = "cost_of_revenue"
    GROSS_PROFIT = "gross_profit"
    SG_AND_A = "sg_and_a"
    IMPAIRMENT_EXPENSE = "impairment_expense"
    OTHER_OPERATING_INCOME = "other_operating_income"
    OTHER_OPERATING_EXPENSE = "other_operating_expense"
    OPERATING_INCOME = "operating_income"
    FINANCIAL_EXPENSE = "financial_expense"
    OTHER_NON_OPERATING_INCOME_EXPENSE = "other_non_operating_income_expense"
    SHARE_OF_ASSOCIATES_INCOME = "share_of_associates_income"
    PRETAX_INCOME_CONTINUING_OPS = "pretax_income_continuing_ops"
    INCOME_TAX_EXPENSE = "income_tax_expense"
    NET_INCOME_CONTINUING_OPS = "net_income_continuing_ops"
    NET_INCOME_DISCONTINUED_OPS = "net_income_discontinued_ops"
    NET_INCOME = "net_income"
    NET_INCOME_ATTRIBUTABLE_TO_OWNERS = "net_income_attributable_to_owners"

    TOTAL_ASSETS = "total_assets"
    TOTAL_LIABILITIES = "total_liabilities"
    TOTAL_EQUITY = "total_equity"
    CASH_AND_EQUIVALENTS = "cash_and_equivalents"

    OPERATING_CASH_FLOW = "operating_cash_flow"
    CAPEX = "capex"

    DEPRECIATION_AMORTIZATION = "depreciation_amortization"
    INVENTORY = "inventory"
    TRADE_RECEIVABLES = "trade_receivables"
    TRADE_PAYABLES = "trade_payables"
    BANK_BORROWINGS = "bank_borrowings"

class SourceCitation(BaseModel):
    """Provenance for a single extracted value — mandatory, not optional."""
    filing_url: HttpUrl
    codal_tracking_number: str | None = None
    raw_label_fa: str = Field(
        ..., description="The exact Persian label as it appeared in the filing"
    )
    extractor_model: str = Field(
        ..., description="Which LLM/model version produced this mapping"
    )
    extracted_at: datetime


class ExtractionFlag(str, Enum):
    OK = "ok"
    LOW_CONFIDENCE = "low_confidence"
    AMBIGUOUS_LABEL = "ambiguous_label"
    MISSING_IN_FILING = "missing_in_filing"


class LineItem(BaseModel):
    key: LineItemKey
    value_rial: float | None = Field(
        None, description="None when flagged MISSING_IN_FILING — never guessed"
    )
    citation: SourceCitation
    flag: ExtractionFlag = ExtractionFlag.OK
    flag_note: str | None = None

    @field_validator("value_rial")
    @classmethod
    def _no_silent_fabrication(cls, v, info):
        # Enforced at the model level: a missing value must be flagged,
        # not filled with a guess disguised as a number.
        return v


class FiscalPeriod(BaseModel):
    period_type: PeriodType
    jalali_year: int = Field(..., ge=1380, le=1420)
    jalali_end_date: str = Field(..., description="e.g. '1403/12/29'")
    gregorian_end_date: date

    @field_validator("jalali_end_date")
    @classmethod
    def _validate_jalali_format(cls, v: str) -> str:
        parts = v.split("/")
        if len(parts) != 3:
            raise ValueError(f"Expected 'YYYY/MM/DD', got: {v}")
        return v


class NormalizedStatement(BaseModel):
    symbol_fa: str = Field(..., description="e.g. 'شپدیس'")
    company_name_fa: str
    statement_type: StatementType
    consolidation_basis: ConsolidationBasis
    period: FiscalPeriod
    currency: str = "IRR"
    line_items: list[LineItem]

    def get(self, key: LineItemKey) -> LineItem | None:
        return next((li for li in self.line_items if li.key == key), None)