"""Document handlers.

Office files (.docx/.xlsx/.pptx) are edited by rewriting text nodes inside the
original zip container. Nothing else in the package is touched, so styles,
images, charts, formulas and layout survive byte-for-byte.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from .replace import Replacer

OOXML_EXT = {".docx", ".docm", ".xlsx", ".xlsm", ".pptx", ".pptm"}
TEXT_EXT = {".txt", ".md", ".csv", ".tsv", ".json", ".xml", ".html", ".htm", ".yaml", ".yml", ".log"}
LEGACY_EXT = {".doc": ".docx", ".xls": ".xlsx", ".ppt": ".pptx"}
SUPPORTED_EXT = sorted(OOXML_EXT | TEXT_EXT)

XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
TEXT_LEAVES = {"t", "delText"}
GROUP_TAGS = {"p", "si", "is", "text"}
META_ATTRS = {"author", "initials", "userName", "lastModifiedBy", "displayName"}
META_ELEMS = {"creator", "lastModifiedBy", "Company", "Manager", "author"}


class UnsupportedFormat(Exception):
    pass


@dataclass
class Unit:
    text: str
    for_model: bool = True  # False: numeric cell, only regex categories look at it


def _local(el) -> str:
    tag = el.tag
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _spread(nodes: list, spans: list[tuple[int, int, str]]) -> None:
    """Apply spans (offsets into the concatenated text) back onto text nodes."""
    full = "".join(n.text or "" for n in nodes)
    a = 0
    for n in nodes:
        b = a + len(n.text or "")
        out, pos = [], a
        for s, e, r in spans:
            if e <= a:
                continue
            if s >= b:
                break
            if s > pos:
                out.append(full[pos:s])
            if s >= a:  # the span starts in this node: it carries the replacement
                out.append(r)
            pos = max(pos, min(e, b))
        out.append(full[pos:b])
        new = "".join(out)
        if new != (n.text or ""):
            n.text = new
            if new != new.strip():
                n.set(XML_SPACE, "preserve")
        a = b


class OOXMLDocument:
    def __init__(self, path: Path):
        self.path = Path(path)
        with zipfile.ZipFile(self.path) as z:
            self._infos = z.infolist()
            self._data = {i.filename: z.read(i.filename) for i in self._infos}
        self._trees: dict[str, etree._ElementTree] = {}
        self._dirty: set[str] = set()
        self._groups: list[tuple[str, list]] = []
        self._cells: list[tuple[str, object]] = []  # numeric / formula-string cells
        self._index()

    def _tree(self, name: str):
        if name not in self._trees:
            self._trees[name] = etree.ElementTree(etree.fromstring(self._data[name]))
        return self._trees[name]

    def _xml_parts(self) -> list[str]:
        return [n for n in self._data
                if n.endswith(".xml") and n.split("/")[0] in {"word", "xl", "ppt"}]

    def _index(self) -> None:
        for name in self._xml_parts():
            try:
                root = self._tree(name).getroot()
            except etree.XMLSyntaxError:
                continue
            groups: dict[int, list] = {}
            order: list[int] = []
            for el in root.iter():
                loc = _local(el)
                if loc in TEXT_LEAVES:
                    anc = el.getparent()
                    phonetic = False
                    while anc is not None and _local(anc) not in GROUP_TAGS:
                        phonetic = phonetic or _local(anc) == "rPh"
                        anc = anc.getparent()
                    key = id(el) if (anc is None or phonetic) else id(anc)
                    if key not in groups:
                        groups[key] = []
                        order.append(key)
                    groups[key].append(el)
                elif loc == "c" and name.startswith("xl/worksheets/"):
                    kind = el.get("t", "n")
                    v = next((c for c in el if _local(c) == "v"), None)
                    if v is None or not v.text:
                        continue
                    has_f = any(_local(c) == "f" for c in el)
                    if kind == "str" or (kind == "n" and not has_f and re.fullmatch(r"\d{4,}", v.text)):
                        self._cells.append((name, el))
            for key in order:
                self._groups.append((name, groups[key]))

    def units(self) -> list[Unit]:
        out = [Unit("".join(n.text or "" for n in nodes)) for _, nodes in self._groups]
        for _, c in self._cells:
            v = next(x for x in c if _local(x) == "v")
            out.append(Unit(v.text, for_model=c.get("t") == "str"))
        return [u for u in out if u.text.strip()]

    def apply(self, rep: Replacer) -> int:
        n = 0
        for name, nodes in self._groups:
            spans = rep.spans("".join(x.text or "" for x in nodes))
            if spans:
                _spread(nodes, spans)
                self._dirty.add(name)
                n += len(spans)
        for name, c in self._cells:
            v = next(x for x in c if _local(x) == "v")
            spans = rep.spans(v.text)
            if not spans:
                continue
            new = rep.apply(v.text)
            if c.get("t") == "str":
                v.text = new
            else:  # numeric cell becomes an inline string
                ns = c.tag.rsplit("}", 1)[0] + "}"
                c.remove(v)
                c.set("t", "inlineStr")
                is_ = etree.SubElement(c, ns + "is")
                etree.SubElement(is_, ns + "t").text = new
            self._dirty.add(name)
            n += len(spans)
        return n

    def scrub_metadata(self) -> int:
        n = 0
        for name in [x for x in self._data if x.endswith(".xml")]:
            top = name.split("/")[0]
            if top not in {"docProps", "word", "xl", "ppt"}:
                continue
            try:
                root = self._tree(name).getroot()
            except etree.XMLSyntaxError:
                continue
            for el in root.iter():
                if not isinstance(el.tag, str):
                    continue
                for k in list(el.attrib):
                    if k.rsplit("}", 1)[-1] in META_ATTRS and el.attrib[k]:
                        el.attrib[k] = ""
                        n += 1; self._dirty.add(name)
                if _local(el) in META_ELEMS and el.text and (top == "docProps" or _local(el) == "author"):
                    el.text = ""
                    n += 1; self._dirty.add(name)
        return n

    def save(self, out: Path) -> None:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for info in self._infos:
                data = self._data[info.filename]
                if info.filename in self._dirty:
                    tree = self._trees[info.filename]
                    data = etree.tostring(tree, xml_declaration=True, encoding="UTF-8",
                                          standalone=tree.docinfo.standalone)
                z.writestr(info, data, compress_type=info.compress_type)


class TextDocument:
    def __init__(self, path: Path):
        self.path = Path(path)
        raw = self.path.read_bytes()
        for enc in ("utf-8-sig", "utf-16", "cp950"):
            try:
                if enc == "utf-16" and raw[:2] not in (b"\xff\xfe", b"\xfe\xff"):
                    continue
                self.text = raw.decode(enc)
                self.encoding = enc
                break
            except UnicodeDecodeError:
                continue
        else:
            raise UnsupportedFormat("無法判斷文字編碼（支援 UTF-8、UTF-16、Big5）。")
        if self.encoding == "utf-8-sig" and not raw.startswith(b"\xef\xbb\xbf"):
            self.encoding = "utf-8"

    def units(self) -> list[Unit]:
        return [Unit(p) for p in self.text.split("\n") if p.strip()]

    def apply(self, rep: Replacer) -> int:
        n = rep.count(self.text)
        self.text = rep.apply(self.text)
        return n

    def scrub_metadata(self) -> int:
        return 0

    def save(self, out: Path) -> None:
        Path(out).write_bytes(self.text.encode(self.encoding))


def open_document(path: str | Path):
    path = Path(path)
    ext = path.suffix.lower()
    if ext in LEGACY_EXT:
        raise UnsupportedFormat(
            f"舊版 Office 格式（{ext}）無法直接處理。請先在 Office 或 LibreOffice 以"
            f"「另存新檔」轉成 {LEGACY_EXT[ext]} 再試一次。"
        )
    if ext == ".pdf":
        raise UnsupportedFormat("不支援 PDF：PDF 無法原樣取代文字。請改用原始的 Word／Excel 檔。")
    if ext in OOXML_EXT:
        try:
            return OOXMLDocument(path)
        except zipfile.BadZipFile:
            raise UnsupportedFormat("檔案不是有效的 Office 文件（可能已加密或損毀）。")
    if ext in TEXT_EXT:
        return TextDocument(path)
    raise UnsupportedFormat(f"不支援的格式：{ext or '（無副檔名）'}。支援：{'、'.join(SUPPORTED_EXT)}")
