from datetime import date
from pathlib import Path

from tse_valuator.ingestion.schema import (
    ConsolidationBasis,
    FiscalPeriod,
    LineItemKey,
    PeriodType,
    StatementType,
)
from tse_valuator.ingestion.statement_builder import build_normalized_statement

FIXTURE = Path(__file__).parent / "fixtures" / "shapadis_annual_1404.xlsx"


def test_end_to_end_builds_statement_with_correct_revenue():
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

    assert result.statement is not None
    revenue_item = result.statement.get(LineItemKey.REVENUE)
    assert revenue_item is not None
    assert revenue_item.value_rial == 600_474_556

    # We expect some unmapped labels at this stage — that's honest and
    # correct given our lookup table is intentionally minimal so far.
    assert isinstance(result.unmapped_labels, list)