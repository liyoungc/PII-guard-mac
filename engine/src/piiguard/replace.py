"""Find non-overlapping replacement spans for a set of known values."""
from __future__ import annotations

import re


def _pattern_for(value: str) -> str:
    pat = re.escape(value)
    # ASCII alphanumerics need boundaries so "123456" never matches inside
    # "91234567"; CJK text has no word boundaries, so match anywhere.
    if value[:1].isascii() and value[:1].isalnum():
        pat = r"(?<![A-Za-z0-9])" + pat
    if value[-1:].isascii() and value[-1:].isalnum():
        pat = pat + r"(?![A-Za-z0-9])"
    return pat


class Replacer:
    def __init__(self, mapping: dict[str, str]):
        self.mapping = {k: v for k, v in mapping.items() if k}
        keys = sorted(self.mapping, key=len, reverse=True)  # longest first
        self._rx = re.compile("|".join(_pattern_for(k) for k in keys)) if keys else None

    def spans(self, text: str) -> list[tuple[int, int, str]]:
        if not self._rx or not text:
            return []
        return [(m.start(), m.end(), self.mapping[m.group(0)]) for m in self._rx.finditer(text)]

    def apply(self, text: str) -> str:
        out, pos = [], 0
        for s, e, r in self.spans(text):
            out.append(text[pos:s]); out.append(r); pos = e
        out.append(text[pos:])
        return "".join(out)

    def count(self, text: str) -> int:
        return len(self.spans(text))
