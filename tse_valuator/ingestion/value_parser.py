"""
Parses raw Codal numeric strings into Python floats.

Handles three conventions seen in real Codal exports:
- Persian-Indic digits (۰-۹) instead of ASCII digits
- Thousands separators (commas)
- Negative values shown as (parentheses) rather than a minus sign

Units: Codal financial statement values are conventionally in millions
of rials unless otherwise stated in the filing's own header/notes. This
module does NOT apply any unit conversion — it returns the number
exactly as scaled in the source cell. Unit handling (millions vs. rials
vs. EPS-in-rial) is a downstream concern, made explicit rather than
silently assumed here.
"""

from __future__ import annotations

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ASCII_DIGITS = "0123456789"
_DIGIT_TRANSLATION = str.maketrans(PERSIAN_DIGITS, ASCII_DIGITS)


class UnparsableValueError(Exception):
    """Raised when a raw value string can't be parsed as a number —
    surfaced explicitly, never silently coerced to 0 or None."""

    def __init__(self, raw_value: str):
        self.raw_value = raw_value
        super().__init__(f"Cannot parse as a number: {raw_value!r}")


def parse_codal_number(raw_value: str) -> float | None:
    """
    Parses a single Codal numeric cell into a float.

    Returns None for cells that are legitimately blank (empty string,
    or Codal's own placeholder for "not applicable", e.g. '--').
    Raises UnparsableValueError for anything else that isn't a
    recognizable number — we do not guess.
    """
    if raw_value is None:
        return None

    cleaned = raw_value.strip()

    if cleaned == "" or cleaned == "--" or cleaned == "-":
        return None

    is_negative = cleaned.startswith("(") and cleaned.endswith(")")
    if is_negative:
        cleaned = cleaned[1:-1]

    cleaned = cleaned.translate(_DIGIT_TRANSLATION)
    cleaned = cleaned.replace(",", "").replace("٬", "")  # ASCII and Persian thousands separators

    try:
        value = float(cleaned)
    except ValueError as e:
        raise UnparsableValueError(raw_value) from e

    return -value if is_negative else value