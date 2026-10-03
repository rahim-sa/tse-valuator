"""
Real-terms (CPI-deflated) and USD-shadow currency adjustments for
rial-denominated financial statement values.

Both functions here are pure math over plain inputs (a CPI series, an
FX rate) -- they do NOT fetch data themselves. Fetching lives in
macro/cpi_client.py and macro/fx_client.py; this module only combines
already-fetched data, which keeps it fully offline-testable and keeps
"what data did we use" separate from "what did we compute with it" --
both individually auditable.

APPROXIMATION NOTE: Iran's fiscal year (based on the Jalali calendar,
roughly ending in September for companies like شپدیس, or ending at
Nowruz/late March for calendar-year filers) does not align exactly
with the Gregorian calendar year that World Bank CPI data is published
for. We map a fiscal period to the Gregorian year of its END date as a
reasonable approximation, not an exact match. This is stated here
explicitly rather than silently assumed.
"""

from __future__ import annotations


def deflate_to_real(
    nominal_value: float,
    from_year: int,
    to_base_year: int,
    cpi_series: dict[int, float],
) -> float:
    """
    Converts a nominal rial value from `from_year` into real terms,
    expressed in `to_base_year` purchasing power, using a CPI index
    series (level, e.g. World Bank FP.CPI.TOTL, base=100 in some
    reference year -- the reference year itself doesn't matter here,
    only the RATIO between from_year and to_base_year does).

    Raises KeyError if either year is missing from cpi_series -- we do
    not silently substitute a nearby year.
    """
    if from_year not in cpi_series:
        raise KeyError(f"CPI data missing for year {from_year}")
    if to_base_year not in cpi_series:
        raise KeyError(f"CPI data missing for year {to_base_year}")

    ratio = cpi_series[to_base_year] / cpi_series[from_year]
    return nominal_value * ratio


def convert_rial_to_usd(rial_value: float, usd_irr_rate: float) -> float:
    """
    Converts a nominal rial value to USD using a given free-market
    USD/IRR rate (rial per 1 USD). No inflation adjustment happens
    here -- this is a currency conversion at a point-in-time rate, a
    separate concern from deflate_to_real above. Combine both
    deliberately if you want real-USD terms, don't conflate them.
    """
    if usd_irr_rate <= 0:
        raise ValueError(f"usd_irr_rate must be positive, got {usd_irr_rate}")
    return rial_value / usd_irr_rate