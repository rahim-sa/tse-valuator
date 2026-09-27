from datetime import date, datetime

import pytest
from pydantic import ValidationError

from tse_valuator.ingestion.schema import (
    ConsolidationBasis,
    ExtractionFlag,
    FiscalPeriod,
    LineItem,
    LineItemKey,
    NormalizedStatement,
    PeriodType,
    SourceCitation,
    StatementType,
)


def _citation(**overrides) -> SourceCitation:
    defaults = dict(
        filing_url="https://www.codal.ir/Reports/Decision.aspx?LetterSerial=abc123",
        codal_tracking_number="abc123",
        raw_label_fa="درآمدهای عملیاتی",
        extractor_model="claude-sonnet-4-6",
        extracted_at=datetime(2025, 6, 1, 12, 0, 0),
    )
    defaults.update(overrides)
    return SourceCitation(**defaults)


def test_valid_statement_round_trips():
    stmt = NormalizedStatement(
        symbol_fa="شپدیس",
        company_name_fa="پتروشیمی پردیس",
        statement_type=StatementType.INCOME_STATEMENT,
        consolidation_basis=ConsolidationBasis.STANDALONE,
        period=FiscalPeriod(
            period_type=PeriodType.ANNUAL,
            jalali_year=1403,
            jalali_end_date="1403/12/29",
            gregorian_end_date=date(2025, 3, 19),
        ),
        line_items=[
            LineItem(
                key=LineItemKey.REVENUE,
                value_rial=52_000_000_000_000,
                citation=_citation(),
            ),
        ],
    )
    assert stmt.get(LineItemKey.REVENUE).value_rial == 52_000_000_000_000
    assert stmt.get(LineItemKey.NET_INCOME) is None


def test_missing_value_must_be_flagged_not_silent():
    # A None value paired with MISSING_IN_FILING is valid — this is how
    # "we genuinely don't know" is supposed to look downstream.
    item = LineItem(
        key=LineItemKey.CAPEX,
        value_rial=None,
        citation=_citation(raw_label_fa="مخارج سرمایه‌ای"),
        flag=ExtractionFlag.MISSING_IN_FILING,
        flag_note="Not disclosed separately in this filing's cash flow statement",
    )
    assert item.value_rial is None
    assert item.flag == ExtractionFlag.MISSING_IN_FILING


def test_bad_jalali_date_format_rejected():
    with pytest.raises(ValidationError):
        FiscalPeriod(
            period_type=PeriodType.ANNUAL,
            jalali_year=1403,
            jalali_end_date="1403-12-29",  # wrong separator
            gregorian_end_date=date(2025, 3, 19),
        )


def test_citation_requires_valid_url():
    with pytest.raises(ValidationError):
        _citation(filing_url="not-a-url")