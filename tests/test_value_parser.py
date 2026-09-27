import pytest

from tse_valuator.ingestion.value_parser import (
    UnparsableValueError,
    parse_codal_number,
)


def test_persian_digits_with_thousands_separator():
    # Revenue from the fixture filing
    assert parse_codal_number("۶۰۰,۴۷۴,۵۵۶") == 600_474_556


def test_negative_value_in_parentheses():
    # Cost of revenue from the fixture filing — shown as (۳۰۳,۱۷۲,۲۸۷)
    assert parse_codal_number("(۳۰۳,۱۷۲,۲۸۷)") == -303_172_287


def test_zero_value():
    assert parse_codal_number("۰") == 0


def test_blank_returns_none():
    assert parse_codal_number("") is None


def test_dash_placeholder_returns_none():
    assert parse_codal_number("--") is None


def test_none_input_returns_none():
    assert parse_codal_number(None) is None


def test_garbage_raises_explicitly():
    with pytest.raises(UnparsableValueError):
        parse_codal_number("این عدد نیست")