"""
Normalizes Persian/Arabic text so visually-identical characters compare
equal. Codal filings inconsistently mix Arabic-script codepoints
(originally designed for Arabic) with true Persian codepoints, plus
inconsistent zero-width non-joiner usage in compound words. Without
this, exact-string label matching silently fails even when a human
would read the two strings as identical.
"""

from __future__ import annotations

# Arabic-script codepoint -> Persian-script codepoint
_CHAR_MAP = {
    "\u064a": "\u06cc",  # Arabic yeh (ي) -> Persian yeh (ی)
    "\u0643": "\u06a9",  # Arabic kaf (ك) -> Persian kaf (ک)
    "\u0629": "\u0647",  # Arabic teh marbuta (ة) -> heh (ه) — rare, but seen in some filings
}

_ZWNJ = "\u200c"


def normalize_fa(text: str) -> str:
    """
    Normalizes a Persian string for comparison purposes:
    - Maps Arabic-script lookalike characters to their Persian equivalents
    - Collapses/removes zero-width non-joiners (treats ZWNJ-joined and
      space-joined or unjoined compounds as equivalent)
    - Strips leading/trailing whitespace and collapses internal whitespace

    This is for MATCHING only — never use this to rewrite text that will
    be shown to a user or stored as the "original" label; always keep the
    raw label alongside the normalized one for citations/provenance.
    """
    for arabic_char, persian_char in _CHAR_MAP.items():
        text = text.replace(arabic_char, persian_char)

    text = text.replace(_ZWNJ, "")
    text = " ".join(text.split())  # collapse whitespace, strip ends

    return text