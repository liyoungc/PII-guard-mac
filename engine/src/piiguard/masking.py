"""Turn accepted entities into replacement strings according to the mode."""
from __future__ import annotations

from .surname import split_surname

MODES = ("keep_surname", "keep_surname_numbered", "full", "code")
MODE_LABELS = {
    "keep_surname": "留姓（王小明 → 王○○）",
    "keep_surname_numbered": "留姓＋編號（同姓不同人：王○○(1)、王○○(2)）",
    "full": "全遮（王小明 → ○○○）",
    "code": "代號（王小明 → 人員A）",
}


def _mask_chars(text: str, mask: str) -> str:
    return "".join(ch if ch.isspace() else mask for ch in text)


def _code(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return "人員" + s


def build_replacements(entities: list[dict], mode: str, mask: str) -> dict[str, str]:
    """entities: [{"value": str, "type": str}] in first-seen order.

    Returns {original value: replacement}. Non-person entities are always
    fully masked; the mode only governs person names.
    """
    if mode not in MODES:
        raise ValueError(f"unknown mode: {mode}")
    out: dict[str, str] = {}
    persons = [e["value"] for e in entities if e["type"] == "person"]
    for e in entities:
        if e["type"] != "person":
            out[e["value"]] = _mask_chars(e["value"], mask)

    if mode == "full":
        for v in persons:
            out[v] = _mask_chars(v, mask)
    elif mode == "code":
        for i, v in enumerate(dict.fromkeys(persons)):
            out[v] = _code(i)
    else:
        base = {}
        for v in persons:
            sur, rest = split_surname(v)
            base[v] = sur + _mask_chars(rest, mask)
        if mode == "keep_surname_numbered":
            groups: dict[str, list[str]] = {}
            for v in dict.fromkeys(persons):
                groups.setdefault(base[v], []).append(v)
            for masked, members in groups.items():
                if len(members) > 1:
                    for n, v in enumerate(members, 1):
                        base[v] = f"{masked}({n})"
        out.update(base)
    return out
