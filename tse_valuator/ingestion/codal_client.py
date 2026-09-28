"""
Thin wrapper around codal_tsetmc (search) and a direct requests.Session
(Excel download). We use our own session with a real browser User-Agent
because Codal's edge/WAF resets connections that don't look like a
browser — codal_tsetmc's own download path is untested by us and we
don't want to depend on it silently working.

Every outbound call goes through a shared RateLimiter and retries
transient failures with backoff — see rate_limit.py for why.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests
from codal_tsetmc import CodalQuery

from tse_valuator.ingestion.rate_limit import RateLimiter, retry_with_backoff

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.codal.ir/",
}

# Shared across all calls from this process — Codal's rate limiting is
# almost certainly IP-based, so every request we make counts against it,
# regardless of which company/filing it's for.
_rate_limiter = RateLimiter(min_interval_seconds=3.0)


@dataclass
class FilingMetadata:
    tracing_no: int
    symbol: str
    company_name: str
    title: str
    excel_url: str
    is_consolidated: bool
    is_audited: bool


def search_filings(
    symbol: str,
    from_jdate: str,
    letter_group: str = "اطلاعات و صورت مالی سالانه",
) -> list[FilingMetadata]:
    """Searches Codal for a company's filings via codal_tsetmc."""

    def _do_search():
        _rate_limiter.wait()
        query = CodalQuery()
        query.set_symbol(symbol)
        query.set_from_date(from_jdate)
        query.set_letter_group(letter_group)
        query.set_not_audited(False)
        return query.get_api_multi_page()

    raw_results = retry_with_backoff(
        _do_search,
        retryable_exceptions=(Exception,),  # codal_tsetmc raises a bare Exception; see note below
        max_attempts=3,
        base_delay_seconds=10.0,
    )

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

    def _do_download():
        _rate_limiter.wait()
        session = requests.Session()
        session.headers.update(_BROWSER_HEADERS)
        resp = session.get(excel_url, timeout=timeout)
        resp.raise_for_status()
        return resp.content

    return retry_with_backoff(
        _do_download,
        retryable_exceptions=(requests.exceptions.HTTPError, requests.exceptions.ConnectionError),
        max_attempts=3,
        base_delay_seconds=10.0,
    )