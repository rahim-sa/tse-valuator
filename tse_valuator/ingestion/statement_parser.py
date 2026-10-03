"""
Parses Codal's "Excel" export -- which is actually an HTML file using
Microsoft's legacy "Excel Workbook Frameset" format, not a real .xlsx
(ZIP) file. This is why openpyxl can't open it directly; we treat it
as HTML.

IMPORTANT: Codal filings commonly contain BOTH a consolidated and a
parent-company-standalone version of each statement, as separate
tables with IDENTICAL internal structure and no distinguishing text
inside the table itself -- confirmed against a real خصدرا filing,
where two income statement tables returned different revenue figures
and were indistinguishable without looking at the HEADING TEXT
immediately preceding each table (e.g. "صورت سود و زيان تلفيقي"
[consolidated] vs "صورت سود و زيان" [standalone, no "تلفیقی" qualifier]).
This module now captures that preceding heading per section, so
callers can filter to the correct consolidation basis.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bs4 import BeautifulSoup, NavigableString


@dataclass
class RawStatementSection:
    """One statement (income statement, balance sheet, etc.) as raw,
    unmapped label -> value rows, exactly as Codal labeled them."""
    title_fa: str
    heading_fa: str  # the nearest preceding heading text, e.g. "صورت سود و زيان تلفيقي"
    column_headers: list[str]
    rows: dict[str, list[str]] = field(default_factory=dict)

    @property
    def is_consolidated(self) -> bool:
        return "تلفیقی" in self.heading_fa or "تلفيقي" in self.heading_fa


def parse_codal_excel_export(html_bytes: bytes) -> list[RawStatementSection]:
    """
    Parses a Codal 'Excel' export (actually HTML) into a list of raw
    statement sections, each tagged with its nearest preceding heading
    so callers can distinguish consolidated vs. standalone tables.
    """
    soup = BeautifulSoup(html_bytes, "lxml")
    sections: list[RawStatementSection] = []

    current_heading = ""

    for element in soup.find_all(True):
        if element.name != "table":
            if isinstance(element, NavigableString):
                continue
            if not element.find_all():  # leaf element -- a real candidate for heading text
                text = element.get_text(strip=True)
                if text and len(text) < 100:
                    current_heading = text
            continue

        # element.name == "table"
        table = element
        rows = table.find_all("tr")
        if not rows:
            continue

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
            heading_fa=current_heading,
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