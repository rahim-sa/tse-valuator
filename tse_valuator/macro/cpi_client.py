"""
Fetches Iran's CPI index (2010=100) from the World Bank API.

We use the World Bank's FP.CPI.TOTL indicator (index level, not just
year-over-year % change) because deflating a nominal value to real
terms requires dividing by an index RATIO between two periods, which
needs level data, not growth rates alone.

Source: IMF International Financial Statistics, via World Bank
(CC BY-4.0). We prefer this over Iran's own Statistical Center /
Central Bank because those two domestic agencies have been reported to
publish conflicting inflation figures -- a real, citable data-quality
issue, not paranoia. The World Bank/IMF series is a single, consistent,
internationally-curated source, at the cost of being annual-only (no
monthly/quarterly granularity) and subject to its own revision lag.
"""

from __future__ import annotations

import requests

_CPI_URL = "https://api.worldbank.org/v2/country/IRN/indicator/FP.CPI.TOTL"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
}


class CpiDataUnavailableError(Exception):
    """Raised when no CPI value exists for the requested Gregorian year --
    surfaced explicitly rather than silently defaulting to some other year."""

    def __init__(self, year: int):
        self.year = year
        super().__init__(f"No CPI data available for year {year}")


def fetch_iran_cpi_annual(start_year: int = 2000, end_year: int = 2026) -> dict[int, float]:
    """
    Returns {gregorian_year: cpi_index_value}, for years where data exists.
    Years with a null value in the source (common for the most recent
    1-2 years, not yet published) are simply omitted, not zero-filled.
    """
    params = {
        "format": "json",
        "date": f"{start_year}:{end_year}",
        "per_page": "200",
    }
    resp = requests.get(_CPI_URL, params=params, headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    payload = resp.json()

    if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
        return {}

    result: dict[int, float] = {}
    for entry in payload[1]:
        value = entry.get("value")
        year_str = entry.get("date")
        if value is not None and year_str is not None:
            result[int(year_str)] = float(value)

    return result


def get_cpi_for_year(cpi_series: dict[int, float], year: int) -> float:
    """Looks up a single year's CPI value, raising explicitly if absent."""
    if year not in cpi_series:
        raise CpiDataUnavailableError(year)
    return cpi_series[year]