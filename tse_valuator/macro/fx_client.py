"""
Fetches historical free-market USD/IRR exchange rates.

Source: community-maintained archive of bon-bast.com data
(github.com/SamadiPour/rial-exchange-rates-archive), fetched via
raw.githubusercontent.com. We use this over bon-bast.com's own API
because that API is a paid commercial license whose terms forbid use
in a "competing product" -- this archive is a free, unofficial mirror
of the same underlying data.

IMPORTANT UNIT NOTE: the source data is in Toman (1 Toman = 10 Rial).
This function returns values in RIAL to match our schema's currency
convention (see schema.py, NormalizedStatement.currency = "IRR").
"""

from __future__ import annotations

from datetime import timedelta

import jdatetime
import requests

_ARCHIVE_BASE = "https://raw.githubusercontent.com/SamadiPour/rial-exchange-rates-archive/main/jalali"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
}

TOMAN_TO_RIAL = 10


class FxDataUnavailableError(Exception):
    """Raised when no rate is found within the search window -- never
    silently falls back to a wildly different date without saying so."""

    def __init__(self, jalali_date: str, window_days: int):
        self.jalali_date = jalali_date
        super().__init__(
            f"No USD/IRR rate found within {window_days} days of {jalali_date}"
        )


def _fetch_month(jalali_year: int, jalali_month: int) -> dict:
    url = f"{_ARCHIVE_BASE}/{jalali_year}/{jalali_month:02d}/full"
    resp = requests.get(url, headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def get_usd_irr_rate(jalali_date: str, rate_type: str = "sell", window_days: int = 7) -> float:
    """
    Returns the free-market USD/IRR rate (in RIAL) for the given Jalali
    date ("YYYY/MM/DD"). If the exact date has no data (e.g. a market
    holiday), searches up to `window_days` before and after for the
    nearest available date. Raises FxDataUnavailableError if nothing
    is found within that window -- we do not silently substitute an
    arbitrarily distant date.
    """
    jy, jm, jd = (int(p) for p in jalali_date.split("/"))
    target = jdatetime.date(jy, jm, jd)

    for offset in range(0, window_days + 1):
        for candidate in ({target + timedelta(days=offset)} if offset == 0
                           else {target + timedelta(days=offset), target - timedelta(days=offset)}):
            try:
                month_data = _fetch_month(candidate.year, candidate.month)
            except requests.exceptions.HTTPError:
                continue

            date_key = f"{candidate.year}/{candidate.month:02d}/{candidate.day:02d}"
            entry = month_data.get(date_key)
            if entry is not None:
                toman_value = entry["usd"][rate_type]
                return toman_value * TOMAN_TO_RIAL

    raise FxDataUnavailableError(jalali_date, window_days)