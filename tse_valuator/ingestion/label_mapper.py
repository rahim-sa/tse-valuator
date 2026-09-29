"""
Maps Codal's raw Persian statement labels to our canonical LineItemKey
enum. This is a static, human-curated lookup table — NOT an LLM call —
because Codal's labels come from a small, regulatory-standard chart of
accounts, not freeform company-specific text.

Labels are matched via normalize_fa() so that Arabic/Persian codepoint
variants and inconsistent zero-width non-joiners don't cause silent
lookup failures (see text_normalize.py).

Unmapped labels are returned as-is (see `map_label`) so callers can
decide how to handle them — logging, flagging for human review, or
(eventually) an LLM-assisted mapping step for genuinely novel labels.
We are NOT wiring that fallback yet; this module's contract is: known
labels map correctly, unknown labels are reported, never guessed.
"""

from __future__ import annotations

from tse_valuator.ingestion.schema import LineItemKey
from tse_valuator.ingestion.text_normalize import normalize_fa

# Verified against a real filing (tests/fixtures/shapadis_annual_1404.xlsx).
# Extend this table deliberately as we encounter more filings/industries —
# do not let anything silently auto-map an unfamiliar label.

# LABEL_TO_KEY: dict[str, LineItemKey] = {
#     "درآمدهاي عملياتي": LineItemKey.REVENUE,
#     "بهاى تمام شده درآمدهاي عملياتي": LineItemKey.COST_OF_REVENUE,
#     "سود(زيان) ناخالص": LineItemKey.GROSS_PROFIT,
#     "سود(زيان) عملياتى": LineItemKey.OPERATING_INCOME,
#     "سود(زيان) خالص": LineItemKey.NET_INCOME,
#     "جمع دارايي‌ها": LineItemKey.TOTAL_ASSETS,
#     "جمع بدهي‌ها": LineItemKey.TOTAL_LIABILITIES,
#     "جمع حقوق مالکانه": LineItemKey.TOTAL_EQUITY,
#     "موجودي نقد": LineItemKey.CASH_AND_EQUIVALENTS,
#     "جريان ‌خالص ‌ورود‌ (خروج) ‌نقد حاصل از فعاليت‌هاي ‌عملياتي": LineItemKey.OPERATING_CASH_FLOW,
#     "پرداخت‌هاي نقدي براي خريد دارايي‌هاي ثابت مشهود": LineItemKey.CAPEX,
# }

LABEL_TO_KEY: dict[str, LineItemKey] = {
    "درآمدهاي عملياتي": LineItemKey.REVENUE,
    "بهاى تمام شده درآمدهاي عملياتي": LineItemKey.COST_OF_REVENUE,
    "سود(زيان) ناخالص": LineItemKey.GROSS_PROFIT,
    "هزينه‏هاى فروش، ادارى و عمومى": LineItemKey.SG_AND_A,
    "هزينه کاهش ارزش دريافتني‏ها (هزينه استثنايي)": LineItemKey.IMPAIRMENT_EXPENSE,
    "ساير درآمدها": LineItemKey.OTHER_OPERATING_INCOME,
    "ساير هزينه‌ها": LineItemKey.OTHER_OPERATING_EXPENSE,
    "سود(زيان) عملياتى": LineItemKey.OPERATING_INCOME,
    "هزينه‏هاى مالى": LineItemKey.FINANCIAL_EXPENSE,
    "ساير درآمدها و هزينه‏هاى غيرعملياتى": LineItemKey.OTHER_NON_OPERATING_INCOME_EXPENSE,
    "سهم گروه از سود شرکت‌هاي وابسته": LineItemKey.SHARE_OF_ASSOCIATES_INCOME,
    "سود(زيان) عمليات در حال تداوم قبل از ماليات": LineItemKey.PRETAX_INCOME_CONTINUING_OPS,
    "هزينه ماليات بر درآمد": LineItemKey.INCOME_TAX_EXPENSE,
    "سود(زيان) خالص عمليات در حال تداوم": LineItemKey.NET_INCOME_CONTINUING_OPS,
    "سود (زيان) خالص عمليات متوقف شده": LineItemKey.NET_INCOME_DISCONTINUED_OPS,
    "سود(زيان) خالص": LineItemKey.NET_INCOME,
    "جمع دارايي‌ها": LineItemKey.TOTAL_ASSETS,
    "جمع بدهي‌ها": LineItemKey.TOTAL_LIABILITIES,
    "جمع حقوق مالکانه": LineItemKey.TOTAL_EQUITY,
    "موجودي نقد": LineItemKey.CASH_AND_EQUIVALENTS,
    "جريان ‌خالص ‌ورود‌ (خروج) ‌نقد حاصل از فعاليت‌هاي ‌عملياتي": LineItemKey.OPERATING_CASH_FLOW,
    "پرداخت‌هاي نقدي براي خريد دارايي‌هاي ثابت مشهود": LineItemKey.CAPEX,

    "هزینه استهلاک": LineItemKey.DEPRECIATION_AMORTIZATION,
    "موجودي مواد و کالا": LineItemKey.INVENTORY,
    "دريافتني‌هاي تجاري و ساير دريافتني‌ها": LineItemKey.TRADE_RECEIVABLES,
    "پرداختني‌هاي تجاري و ساير پرداختني‌ها": LineItemKey.TRADE_PAYABLES,
    "تسهیلات دریافتی از بانکها": LineItemKey.BANK_BORROWINGS,

    
}


# Normalized-key index, built once at import time, so lookups are
# insensitive to Arabic/Persian codepoint variants and ZWNJ differences.
_NORMALIZED_LABEL_TO_KEY: dict[str, LineItemKey] = {
    normalize_fa(label): key for label, key in LABEL_TO_KEY.items()
}


class UnmappedLabelError(Exception):
    """Raised when a label has no known mapping — surfaced explicitly,
    never silently skipped or guessed."""

    def __init__(self, label: str):
        self.label = label
        super().__init__(f"No canonical mapping for label: {label!r}")


def map_label(raw_label_fa: str) -> LineItemKey:
    """
    Returns the canonical LineItemKey for a raw Codal label.
    Raises UnmappedLabelError if the label isn't in our known table —
    callers must handle this explicitly (e.g. flag for review), rather
    than the mapper silently returning something wrong.
    """
    key = _NORMALIZED_LABEL_TO_KEY.get(normalize_fa(raw_label_fa))
    if key is None:
        raise UnmappedLabelError(raw_label_fa)
    return key


def try_map_label(raw_label_fa: str) -> LineItemKey | None:
    """Non-raising variant — returns None instead of raising, for
    callers that want to collect all unmapped labels in one pass rather
    than stopping at the first one."""
    return _NORMALIZED_LABEL_TO_KEY.get(normalize_fa(raw_label_fa))