"""
Fetches Iran's country risk premium from Damodaran's periodically-
updated dataset (NYU Stern, freely published).

Iran has no conventional Moody's sovereign rating (sanctions), so it
is NOT in the "ERPs by country" sheet used for rated countries --
Damodaran's own FAQ sheet confirms unrated countries should be looked
up in the "PRS Worksheet" instead (PRS = Political Risk Services, an
alternate country-risk-scoring methodology). Confirmed directly
against the live file: Iran's row there gives Final ERP=13.94%,
Country Risk Premium=9.71%, consistent with mature market premium
(4.23%, same file) + CRP = Final ERP.

This is a periodic research estimate (updated ~annually by the
author), not real-time data -- we fetch the live current file at call
time so we always get his latest published figure, but do not expect
or need this to change frequently.
"""

from __future__ import annotations

import io

import openpyxl
import requests

_DATASET_URL = "https://www.stern.nyu.edu/~adamodar/pc/datasets/ctryprem.xlsx"
_SHEET_NAME = "PRS Worksheet"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
}


class CountryNotFoundError(Exception):
    def __init__(self, country: str):
        self.country = country
        super().__init__(f"Country not found in PRS Worksheet: {country!r}")


def fetch_country_risk_premium(country: str = "Iran") -> dict:
    """
    Returns {'prs_score', 'final_erp', 'country_risk_premium', ...} for
    the given country, read from the PRS Worksheet sheet (for
    unrated/sanctioned countries -- see module docstring).
    """
    resp = requests.get(_DATASET_URL, headers=_HEADERS, timeout=30)
    resp.raise_for_status()

    wb = openpyxl.load_workbook(io.BytesIO(resp.content), data_only=True)
    ws = wb[_SHEET_NAME]

    headers = {cell.column: str(cell.value).strip() for cell in ws[1] if cell.value}

    for row in ws.iter_rows(min_row=2):
        if row[0].value and str(row[0].value).strip().lower() == country.lower():
            return {headers[cell.column]: cell.value for cell in row if cell.column in headers}

    raise CountryNotFoundError(country)