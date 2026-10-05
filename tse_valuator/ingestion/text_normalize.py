"""
Normalizes Persian/Arabic text so visually-identical labels compare
equal. Codal filings inconsistently mix Arabic-script codepoints with
true Persian codepoints, plus inconsistent placement of invisible
characters (zero-width non-joiners, bidirectional marks) and spacing
around compound words -- confirmed by real mismatches between our
hand-typed label table and live filings (e.g. "هزينه ‏هاى..." vs
"هزينه‏هاى..." -- identical words, different internal spacing/marks).

DELIBERATE TRADEOFF: this strips ALL whitespace and invisible marks
for comparison, not just collapses them. That means two labels
differing ONLY in spacing will match as equal, even if a human might
consider that meaningful. For Codal's small, standardized accounting
vocabulary this is judged safe and necessary; it would NOT be a safe
default for general-purpose Persian text matching.
"""

from __future__ import annotations

import re

# Arabic-script codepoint -> Persian-script codepoint
_CHAR_MAP = {
    "\u064a": "\u06cc",  # Arabic yeh (ي) -> Persian yeh (ی)
    "\u0643": "\u06a9",  # Arabic kaf (ك) -> Persian kaf (ک)
    "\u0629": "\u0647",  # Arabic teh marbuta (ة) -> heh (ه)
}

# Invisible/direction-control characters seen in real Codal exports,
# stripped entirely (not just collapsed) for comparison purposes.
_INVISIBLE_CHARS = [
    "\u200c",  # zero-width non-joiner (ZWNJ)
    "\u200f",  # right-to-left mark (RLM)
    "\u200e",  # left-to-right mark (LRM)
    "\ufeff",  # zero-width no-break space / BOM
]

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_fa(text: str) -> str:
    """
    Normalizes a Persian string for MATCHING purposes only -- never use
    this to rewrite text shown to a user or stored as the "original"
    label; always keep the raw label alongside the normalized one for
    citations/provenance.
    """
    for arabic_char, persian_char in _CHAR_MAP.items():
        text = text.replace(arabic_char, persian_char)

    for invisible in _INVISIBLE_CHARS:
        text = text.replace(invisible, "")

    text = _WHITESPACE_RE.sub("", text)  # strip ALL whitespace, not just collapse

    return text

def normalize_fa_chars_only(text: str) -> str:
    """
    Like normalize_fa, but keeps whitespace/spacing intact -- used for
    searching for multi-word headings in running text, where word
    boundaries matter, unlike label-matching where they don't.
    """
    for arabic_char, persian_char in _CHAR_MAP.items():
        text = text.replace(arabic_char, persian_char)
    for invisible in _INVISIBLE_CHARS:
        text = text.replace(invisible, "")
    return text