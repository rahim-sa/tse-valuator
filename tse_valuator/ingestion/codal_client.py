"""
Direct client for Codal's real search API (search.codal.ir/api/search/v2/q)
and Excel export download.

We replaced codal_tsetmc's search here after finding two root causes for
our repeated connection failures, confirmed by reading its source
(codal_tsetmc/tools/api.py):
  1. It calls urllib.request.urlopen() with NO headers at all for Codal
     search requests (a GET_HEADERS_REQUEST dict exists in that file but
     is only used for an unrelated TSETMC function).
  2. Its pagination loop (get_api_multi_page) fires one request per page
     with zero delay between them -- an easy trigger for anti-bot
     rate-limiting.

Both are fixed here: every request uses a real browser User-Agent, and
every request -- including each individual page -- goes through the
shared RateLimiter.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

#from tse_valuator.ingestion.rate_limit import RateLimiter, retry_with_backoff
from tse_valuator.ingestion.rate_limit import RateLimiter, RateLimitExceededError, retry_with_backoff

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.codal.ir/",
    "Accept": "application/json, text/plain, */*",
}

_SEARCH_URL = "https://search.codal.ir/api/search/v2/q"

# Shared across all calls from this process -- Codal's rate limiting is
# almost certainly IP-based, so every request counts against it,
# regardless of which company/filing/page it's for.
_rate_limiter = RateLimiter(min_interval_seconds=3.0)

_session = requests.Session()
_session.headers.update(_BROWSER_HEADERS)


@dataclass
class FilingMetadata:
    tracing_no: int
    symbol: str
    company_name: str
    title: str
    excel_url: str
    is_consolidated: bool
    is_audited: bool


def _fetch_search_page(symbol: str, from_jdate: str, page_number: int) -> dict:
    params = {
        "Symbol": symbol,
        "FromDate": from_jdate,
        "PageNumber": page_number,
        "Audited": "true",
        "NotAudited": "true",
        "Consolidatable": "true",
        "NotConsolidatable": "true",
        "Childs": "true",
        "Mains": "true",
        "Publisher": "false",
        "search": "true",
    }

    # def _do_request():
    #     _rate_limiter.wait()
    #     resp = _session.get(_SEARCH_URL, params=params, timeout=20)
    #     resp.raise_for_status()
    #     return resp.json()

    def _do_request():
        _rate_limiter.wait()
        resp = _session.get(_SEARCH_URL, params=params, timeout=20)
        if resp.status_code == 429:
            raise RateLimitExceededError(resp.url)
        resp.raise_for_status()
        return resp.json()

    return retry_with_backoff(
        _do_request,
        retryable_exceptions=(requests.exceptions.HTTPError, requests.exceptions.ConnectionError),
        max_attempts=3,
        base_delay_seconds=10.0,
    )


def search_filings(symbol: str, from_jdate: str) -> list[FilingMetadata]:
    """
    Searches Codal for a company's filings across all result pages,
    using the real search API directly (see module docstring for why
    we don't use codal_tsetmc's search here).
    """
    first_page = _fetch_search_page(symbol, from_jdate, page_number=1)
    total_pages = first_page.get("Page", 1)
    all_letters = list(first_page.get("Letters", []))

    for page_number in range(2, total_pages + 1):
        page = _fetch_search_page(symbol, from_jdate, page_number)
        all_letters.extend(page.get("Letters", []))

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
        for r in all_letters
        if r.get("ExcelUrl")
    ]


def download_filing_excel(excel_url: str, timeout: int = 30) -> bytes:
    """Downloads a Codal 'Excel' export (actually HTML -- see statement_parser.py)."""

    # def _do_download():
    #     _rate_limiter.wait()
    #     resp = _session.get(excel_url, timeout=timeout)
    #     resp.raise_for_status()
    #     return resp.content
    def _do_download():
        _rate_limiter.wait()
        resp = _session.get(excel_url, timeout=timeout)
        if resp.status_code == 429:
            raise RateLimitExceededError(resp.url)
        resp.raise_for_status()
        return resp.content

    return retry_with_backoff(
        _do_download,
        retryable_exceptions=(requests.exceptions.HTTPError, requests.exceptions.ConnectionError),
        max_attempts=3,
        base_delay_seconds=10.0,
    )