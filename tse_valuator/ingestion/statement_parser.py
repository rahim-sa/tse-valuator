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
immediately preceding each table.

KNOWN LIMITATION: some older filings (confirmed: بترانس fiscal year
1402) bunch all statement-name headings together near the document's
start (like a table of contents) instead of placing them individually
before each table -- for these filings, heading_fa will incorrectly
show generic disclaimer text instead of the real statement name, and
is_consolidated will be unreliable. A fix was attempted (positional
pairing of headings-list order with table order) but found to be
incorrect, since the two orderings don't actually match in at least
one real case -- reverted rather than ship broken logic. Revisit with
a content-based matching approach (matching each table's row labels
against expected statement-type signatures) if this needs solving.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bs4 import BeautifulSoup, NavigableString


@dataclass
class RawStatementSection:
    title_fa: str
    heading_fa: str
    column_headers: list[str]
    rows: dict[str, list[str]] = field(default_factory=dict)

    @property
    def is_consolidated(self) -> bool:
        return "تلفیقی" in self.heading_fa or "تلفيقي" in self.heading_fa


def parse_codal_excel_export(html_bytes: bytes) -> list[RawStatementSection]:
    soup = BeautifulSoup(html_bytes, "lxml")
    sections: list[RawStatementSection] = []

    current_heading = ""

    for element in soup.find_all(True):
        if element.name != "table":
            if isinstance(element, NavigableString):
                continue
            if not element.find_all():
                text = element.get_text(strip=True)
                if text and len(text) < 100:
                    current_heading = text
            continue

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