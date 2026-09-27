"""
Parses Codal's "Excel" export — which is actually an HTML file using
Microsoft's legacy "Excel Workbook Frameset" format, not a real .xlsx
(ZIP) file. This is why openpyxl can't open it directly; we treat it
as HTML.

This module's job stops at: raw label -> raw value pairs, grouped by
statement section. It does NOT map labels to our canonical LineItemKey
enum — that mapping lives in a separate step (label_mapper.py, not yet
written), since it's the part that may need LLM help for label variants
we haven't seen yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bs4 import BeautifulSoup


@dataclass
class RawStatementSection:
    """One statement (income statement, balance sheet, etc.) as raw,
    unmapped label -> value rows, exactly as Codal labeled them."""
    title_fa: str
    column_headers: list[str]
    rows: dict[str, list[str]] = field(default_factory=dict)


def parse_codal_excel_export(html_bytes: bytes) -> list[RawStatementSection]:
    """
    Parses a Codal 'Excel' export (actually HTML) into a list of raw
    statement sections. Each <table> in the file corresponds to one
    statement (income statement, balance sheet, cash flow, etc.)
    """
    soup = BeautifulSoup(html_bytes, "lxml")
    sections: list[RawStatementSection] = []

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue

        # First non-empty row is treated as the header row (column labels).
        # Codal's tables are inconsistent about exactly where the header
        # sits, so we take the first row with more than one populated cell.
        header_cells: list[str] = []
        data_start_idx = 0
        for i, row in enumerate(rows):
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            non_empty = [c for c in cells if c]
            if len(non_empty) > 1:
                header_cells = cells
                data_start_idx = i + 1
                break

        if not header_cells:
            continue

        section = RawStatementSection(
            title_fa=header_cells[0] if header_cells else "",
            column_headers=header_cells[1:],
        )

        for row in rows[data_start_idx:]:
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if not cells or not cells[0]:
                continue
            label, *values = cells
            section.rows[label] = values

        if section.rows:
            sections.append(section)

    return sections