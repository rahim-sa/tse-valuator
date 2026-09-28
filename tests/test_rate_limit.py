import pytest

from tse_valuator.ingestion.rate_limit import RateLimiter, retry_with_backoff


class FakeClock:
    """Lets tests control the passage of time deterministically."""

    def __init__(self):
        self.now = 0.0
        self.sleep_calls: list[float] = []

    def time_fn(self) -> float:
        return self.now

    def sleep_fn(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.now += seconds


def test_rate_limiter_waits_when_called_too_soon():
    clock = FakeClock()
    limiter = RateLimiter(min_interval_seconds=5.0, sleep_fn=clock.sleep_fn, time_fn=clock.time_fn)

    limiter.wait()  # first call, no prior call, no wait
    assert clock.sleep_calls == []

    clock.now += 2.0  # only 2s passed, need 5s
    limiter.wait()
    assert clock.sleep_calls == [3.0]  # should have slept the remaining 3s


def test_rate_limiter_does_not_wait_if_enough_time_passed():
    clock = FakeClock()
    limiter = RateLimiter(min_interval_seconds=5.0, sleep_fn=clock.sleep_fn, time_fn=clock.time_fn)

    limiter.wait()
    clock.now += 10.0  # plenty of time passed
    limiter.wait()
    assert clock.sleep_calls == []


def test_retry_with_backoff_succeeds_on_second_attempt():
    clock = FakeClock()
    attempts = {"count": 0}

    def flaky():
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise ConnectionError("boom")
        return "ok"

    result = retry_with_backoff(
        flaky,
        retryable_exceptions=(ConnectionError,),
        max_attempts=3,
        base_delay_seconds=1.0,
        sleep_fn=clock.sleep_fn,
    )
    assert result == "ok"
    assert attempts["count"] == 2
    assert clock.sleep_calls == [1.0]  # one backoff sleep before the successful 2nd attempt


def test_retry_with_backoff_raises_after_exhausting_attempts():
    def always_fails():
        raise ConnectionError("still broken")

    with pytest.raises(ConnectionError):
        retry_with_backoff(
            always_fails,
            retryable_exceptions=(ConnectionError,),
            max_attempts=3,
            base_delay_seconds=1.0,
            sleep_fn=lambda s: None,  # no real sleeping needed for this test
        )


def test_non_retryable_exception_propagates_immediately():
    attempts = {"count": 0}

    def fails_with_wrong_type():
        attempts["count"] += 1
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        retry_with_backoff(
            fails_with_wrong_type,
            retryable_exceptions=(ConnectionError,),  # ValueError not in this tuple
            max_attempts=3,
            sleep_fn=lambda s: None,
        )
    assert attempts["count"] == 1  # should not have retried at all