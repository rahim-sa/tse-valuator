"""
Thin wrapper around codal_tsetmc (search) and a direct requests.Session
(Excel download). We use our own session with a real browser User-Agent
because Codal's edge/WAF resets connections that don't look like a
browser — codal_tsetmc's own download path is untested by us and we
don't want to depend on it silently working.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests
from codal_tsetmc import CodalQuery

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.codal.ir/",
}


@dataclass
class FilingMetadata:
    tracing_no: int
    symbol: str
    company_name: str
    title: str
    excel_url: str
    is_consolidated: bool  # inferred from title containing "تلفیقی"
    is_audited: bool       # inferred from title containing "حسابرسی شده"


def search_filings(
    symbol: str,
    from_jdate: str,
    letter_group: str = "اطلاعات و صورت مالی سالانه",
) -> list[FilingMetadata]:
    """Searches Codal for a company's filings via codal_tsetmc."""
    query = CodalQuery()
    query.set_symbol(symbol)
    query.set_from_date(from_jdate)
    query.set_letter_group(letter_group)
    query.set_not_audited(False)

    raw_results = query.get_api_multi_page()

    return [
        FilingMetadata(
            tracing_no=r["TracingNo"],
            symbol=r["Symbol"],
            company_name=r["CompanyName"],
            title=r["Title"],
            excel_url=r["ExcelUrl"],
            is_consolidated="تلفیقی" in r["Title"] or "تلفيقي" in r["Title"],
            is_audited="حسابرسی نشده" not in r["Title"],
        )
        for r in raw_results
        if r.get("ExcelUrl")
    ]


def download_filing_excel(excel_url: str, timeout: int = 30) -> bytes:
    """
    Downloads a Codal 'Excel' export (actually HTML — see
    statement_parser.py) using a browser-like session to avoid the
    connection resets we hit with unheadered requests.
    """
    session = requests.Session()
    session.headers.update(_BROWSER_HEADERS)
    resp = session.get(excel_url, timeout=timeout)
    resp.raise_for_status()
    return resp.content