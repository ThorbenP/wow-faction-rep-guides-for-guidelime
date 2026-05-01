"""Replace UTF-8 punctuation that GuideLime renders incorrectly.

GuideLime's tag and comment renderer has caused several visible glitches when
fed multibyte UTF-8 punctuation: empty checkbox for an `[OC]` line starting
with `×` (U+00D7), mojibake for `→` (U+2192) inside the chain index, broken
`[D ...]` tag with em-dash `—` (U+2014). To stay portable we replace the
known offenders with ASCII equivalents and drop everything else outside ASCII
(a small whitelist of German umlauts is kept since they render fine).
"""
from __future__ import annotations

_PUNCT_REPLACEMENTS = {
    '→': '->',
    '←': '<-',
    '↔': '<->',
    '×': 'x',
    '—': '--',
    '–': '-',
    '…': '...',
    '‘': "'",
    '’': "'",
    '“': '"',
    '”': '"',
    ' ': ' ',  # NBSP -> normal space
}
_ALLOWED_UTF8 = set('äöüÄÖÜß')


def safe_text(s: str) -> str:
    """Convert a string to a GuideLime-safe form: replace known bad
    punctuation with ASCII equivalents, drop other non-ASCII characters
    except whitelisted umlauts."""
    if not s:
        return s
    out = []
    for ch in s:
        if ch in _PUNCT_REPLACEMENTS:
            out.append(_PUNCT_REPLACEMENTS[ch])
        elif ord(ch) < 128 or ch in _ALLOWED_UTF8:
            out.append(ch)
        # else: drop silently
    return ''.join(out)


def safe_tag_content(s: str) -> str:
    """Same as `safe_text` but additionally replaces square brackets so
    that quest/NPC names like `[PH] Test NPC` cannot prematurely close a
    surrounding `[QA<id> ...]` or `[TAR<id> ...]` tag.
    """
    return safe_text(s).replace('[', '(').replace(']', ')')
