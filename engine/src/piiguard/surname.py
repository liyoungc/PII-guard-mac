"""Split a personal name into (surname, given name).

This is the one place where domain judgement shapes every output of the
"keep surname" masking modes, so it is kept tiny and isolated.
"""
from __future__ import annotations

# Common Taiwanese compound surnames. Extend freely.
COMPOUND_SURNAMES = frozenset(
    "歐陽 司馬 上官 諸葛 司徒 東方 皇甫 尉遲 公孫 慕容 長孫 宇文 軒轅 令狐 "
    "鍾離 夏侯 端木 范姜 張簡 歐陽".split()
)


def is_cjk(ch: str) -> bool:
    return "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿"


def split_surname(name: str) -> tuple[str, str]:
    """Return (surname, rest).

    TODO(owner): refine the judgement calls below — see README "Surname rules".
      * 4-character names: compound surname (歐陽小明) vs. married double
        surname (陳林美玉 -> keep 陳? keep 陳林?). Default here: only a known
        compound surname counts as 2 characters; otherwise keep 1.
      * Non-CJK names (John Smith): default keeps the first character only.
    """
    name = name.strip()
    if not name:
        return "", ""
    if is_cjk(name[0]):
        if len(name) >= 3 and name[:2] in COMPOUND_SURNAMES:
            return name[:2], name[2:]
        return name[:1], name[1:]
    return name[:1], name[1:]
