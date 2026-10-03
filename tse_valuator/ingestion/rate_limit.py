"""
Rate limiting and retry-with-backoff for Codal requests.

We hit Codal's anti-bot/rate-limiting system firsthand by sending rapid
sequential requests across three companies with no delay between them.
This module is a direct, permanent response to that: every outbound
request to Codal should go through a shared RateLimiter (minimum delay
between requests) and transient failures should retry with exponential
backoff rather than failing immediately or hammering the server again
right away.

Both the delay and sleep mechanisms are injectable so this is fully
testable without actually waiting real wall-clock seconds in tests.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable


class RateLimitExceededError(Exception):
    """
    Raised when Codal itself tells us we're rate-limited (HTTP 429).
    Deliberately NOT included in any retryable_exceptions tuple we pass
    to retry_with_backoff -- when the server has already told us to
    slow down, automatically retrying (even with backoff) is exactly
    the wrong response. This must surface immediately so a human
    decides when to try again.
    """

    def __init__(self, url: str):
        self.url = url
        super().__init__(f"Rate limited (HTTP 429) by: {url}")


class RateLimiter:
    """Enforces a minimum interval between successive calls to `.wait()`."""

    def __init__(
        self,
        min_interval_seconds: float = 2.0,
        sleep_fn: Callable[[float], None] = time.sleep,
        time_fn: Callable[[], float] = time.monotonic,
    ):
        self._min_interval = min_interval_seconds
        self._sleep_fn = sleep_fn
        self._time_fn = time_fn
        self._last_call_time: float | None = None

    def wait(self) -> None:
        """Blocks (via sleep_fn) if needed so at least min_interval_seconds
        has passed since the previous call. Call this immediately before
        making a request."""
        now = self._time_fn()
        if self._last_call_time is not None:
            elapsed = now - self._last_call_time
            remaining = self._min_interval - elapsed
            if remaining > 0:
                self._sleep_fn(remaining)
        self._last_call_time = self._time_fn()


def retry_with_backoff(
    fn: Callable[[], object],
    retryable_exceptions: tuple[type[Exception], ...],
    max_attempts: int = 3,
    base_delay_seconds: float = 5.0,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> object:
    """
    Calls fn(), retrying up to max_attempts times on any exception in
    retryable_exceptions, with exponential backoff (base_delay * 2^attempt).
    Re-raises the final exception if all attempts are exhausted.
    Non-retryable exceptions propagate immediately, unretried.
    """
    last_exception: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return fn()
        except retryable_exceptions as e:
            last_exception = e
            if attempt == max_attempts - 1:
                raise
            delay = base_delay_seconds * (2**attempt)
            sleep_fn(delay)

    # Unreachable, but keeps type-checkers happy
    raise last_exception  # type: ignore[misc]