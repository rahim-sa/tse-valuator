"""
Fetches live market data (current price, shares outstanding) from
TSETMC via pytse-client. Unlike Codal, TSETMC access worked without
rate-limiting/blocking issues when tested directly -- no special
headers or backoff logic needed so far, but we keep error handling
explicit rather than assume this will always be smooth.

This solves a real problem found during testing: our schema has no
"shares outstanding" concept (it's corporate-action data, not a
financial statement line item), and using a stale share count after a
capital increase produced a ~198% valuation error in testing. This
module should be the single source of truth for that number, fetched
fresh each time, never hardcoded.
"""

from __future__ import annotations

import pytse_client as tse


class TickerNotFoundError(Exception):
    def __init__(self, symbol: str):
        self.symbol = symbol
        super().__init__(f"TSETMC ticker not found: {symbol!r}")


def get_current_market_data(symbol_fa: str) -> dict:
    """
    Returns current shares outstanding, EPS, and the most recent close
    price for a given Persian ticker symbol (e.g. "شپدیس").
    """
    try:
        ticker = tse.Ticker(symbol_fa)
    except Exception as e:
        raise TickerNotFoundError(symbol_fa) from e

    history = ticker.history
    if history is None or len(history) == 0:
        raise TickerNotFoundError(symbol_fa)

    latest = history.iloc[-1]

    return {
        "shares_outstanding": ticker.total_shares,
        "eps": ticker.eps,
        "latest_close_rial": latest["close"],
        "latest_date": latest["date"],
    }