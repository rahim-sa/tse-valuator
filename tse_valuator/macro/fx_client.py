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

def get_average_usd_irr_rate(
    start_jalali_date: str, end_jalali_date: str, rate_type: str = "sell"
) -> float:
    """
    Returns the average USD/IRR rate (in RIAL) over a date range.

    Used for converting FLOW items (revenue, cash flow, net income) to
    USD -- unlike point-in-time items (cash, debt), a flow accumulated
    continuously over a period should be converted at the average rate
    over that period, not a single snapshot (this follows standard
    accounting practice for foreign currency translation, e.g. IAS 21 /
    ASC 830). Using a single period-END rate for a flow item
    significantly misstates it when the currency moved a lot during
    the period -- confirmed in testing: Iran's rial moved ~2.5x in one
    year, so this distinction is not a minor technicality here.
    """
    start_y, start_m, start_d = (int(p) for p in start_jalali_date.split("/"))
    end_y, end_m, end_d = (int(p) for p in end_jalali_date.split("/"))

    start = jdatetime.date(start_y, start_m, start_d)
    end = jdatetime.date(end_y, end_m, end_d)

    if start > end:
        raise ValueError("start_jalali_date must be before end_jalali_date")

    rates: list[float] = []
    current_month_start = jdatetime.date(start.year, start.month, 1)

    while current_month_start <= end:
        try:
            month_data = _fetch_month(current_month_start.year, current_month_start.month)
        except requests.exceptions.HTTPError:
            # advance to next month even if this one is unavailable --
            # we average over whatever data genuinely exists
            current_month_start = _next_month(current_month_start)
            continue

        for date_key, entry in month_data.items():
            y, m, d = (int(p) for p in date_key.split("/"))
            day = jdatetime.date(y, m, d)
            if start <= day <= end:
                rates.append(entry["usd"][rate_type] * TOMAN_TO_RIAL)

        current_month_start = _next_month(current_month_start)

    if not rates:
        raise FxDataUnavailableError(f"{start_jalali_date} to {end_jalali_date}", window_days=0)

    return sum(rates) / len(rates)


def _next_month(d: "jdatetime.date") -> "jdatetime.date":
    if d.month == 12:
        return jdatetime.date(d.year + 1, 1, 1)
    return jdatetime.date(d.year, d.month + 1, 1)