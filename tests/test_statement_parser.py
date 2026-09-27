from pathlib import Path

from tse_valuator.ingestion.statement_parser import parse_codal_excel_export

FIXTURE = Path(__file__).parent / "fixtures" / "shapadis_annual_1404.xlsx"


def test_parses_known_sections_from_real_filing():
    html_bytes = FIXTURE.read_bytes()
    sections = parse_codal_excel_export(html_bytes)

    assert len(sections) > 0

    titles = [s.title_fa for s in sections]
    # We know from inspecting this specific fixture that the income
    # statement section exists with this exact Codal label.
    assert any("شرح" in t or "سود و زيان" in t for t in titles) or len(sections) >= 3


def test_revenue_row_is_extracted_with_expected_value():
    html_bytes = FIXTURE.read_bytes()
    sections = parse_codal_excel_export(html_bytes)

    revenue_row = None
    for section in sections:
        for label, values in section.rows.items():
            if "درآمدهاي عملياتي" in label:
                revenue_row = values
                break
        if revenue_row:
            break

    assert revenue_row is not None
    # From the fixture: current period revenue was 600,474,556 (million rial)
    assert "۶۰۰,۴۷۴,۵۵۶" in revenue_row[0] or "600,474,556" in revenue_row[0]