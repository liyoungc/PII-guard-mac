"""scan → (review) → apply → verify."""
from __future__ import annotations

import csv
from pathlib import Path

from . import config as cfgmod
from . import detect, server
from .documents import open_document
from .masking import build_replacements
from .replace import Replacer


def _counts(units, values: list[str]) -> dict[str, int]:
    ident = Replacer({v: v for v in values})
    out = dict.fromkeys(values, 0)
    for u in units:
        for _, _, v in ident.spans(u.text):
            out[v] += 1
    return out


def scan(path: str, cfg: dict, progress=None) -> dict:
    doc = open_document(path)
    units = doc.units()
    wl = cfgmod.whitelist(cfg)
    entities: list[dict] = []
    discarded = 0
    used_model = None

    if cfg["categories"].get("person", True):
        conn = server.connection()
        if not conn or server.status()["state"] != "ready":
            raise detect.ModelError("模型尚未載入。請先在選單載入模型（或執行 piiguard server start）。")
        used_model = conn["model"]
        names, discarded = detect.find_names(units, conn, progress)
        entities += [{"value": n, "type": "person", "source": "model"} for n in names]
    for b in cfg.get("blacklist") or []:
        if b and b not in {e["value"] for e in entities}:
            entities.append({"value": b, "type": "person", "source": "blacklist"})
    for e in detect.find_patterns(units, cfg["categories"], cfg.get("custom_patterns") or []):
        if e["value"] not in {x["value"] for x in entities}:
            entities.append({**e, "source": "pattern"})

    skipped = [e["value"] for e in entities if e["value"] in wl and e["source"] != "blacklist"]
    entities = [e for e in entities if e["value"] not in skipped]
    counts = _counts(units, [e["value"] for e in entities])
    entities = [e for e in entities if counts[e["value"]] > 0]
    repl = build_replacements(entities, cfg["mode"], cfg["mask_char"])
    for e in entities:
        e["count"] = counts[e["value"]]
        e["replacement"] = repl[e["value"]]
    return {"file": str(path), "model": used_model, "entities": entities,
            "whitelisted": skipped, "discarded_model_outputs": discarded,
            "text_units": len(units)}


def preview(entities: list[dict], cfg: dict) -> list[dict]:
    """Recompute replacements after the reviewer edits the list."""
    repl = build_replacements(entities, cfg["mode"], cfg["mask_char"])
    return [{**e, "replacement": repl[e["value"]]} for e in entities]


def default_output(path: Path, suffix: str) -> Path:
    out = path.with_name(f"{path.stem}{suffix}{path.suffix}")
    n = 2
    while out.exists():
        out = path.with_name(f"{path.stem}{suffix}-{n}{path.suffix}")
        n += 1
    return out


def apply(path: str, entities: list[dict], cfg: dict, out: str | None = None) -> dict:
    """entities: accepted items [{"value", "type", optional "replacement"}]."""
    src = Path(path)
    doc = open_document(src)
    ents = [e for e in entities if e.get("value")]
    repl = build_replacements(ents, cfg["mode"], cfg["mask_char"])
    for e in ents:  # a reviewer may override a single replacement by hand
        if e.get("replacement_override"):
            repl[e["value"]] = e["replacement_override"]
    rep = Replacer(repl)
    replaced = doc.apply(rep)
    scrubbed = doc.scrub_metadata() if cfg.get("scrub_metadata", True) else 0
    dst = Path(out) if out else default_output(src, cfg.get("output_suffix") or "_去識別")
    if dst.resolve() == src.resolve():
        raise ValueError("輸出檔不可與原檔相同。")
    doc.save(dst)

    # Independent check: reopen what was written and look for every original value.
    check = open_document(dst)
    residual = _counts(check.units(), list(repl))
    residual = {k: v for k, v in residual.items() if v and repl[k] != k}

    mapping_path = None
    if cfg.get("write_mapping"):
        mapping_path = dst.with_name(f"{dst.stem}_對照表.csv")
        with open(mapping_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["原文", "取代為", "類別"])
            for e in ents:
                w.writerow([e["value"], repl[e["value"]], e["type"]])
    return {"output": str(dst), "replaced": replaced, "metadata_fields_cleared": scrubbed,
            "residual": residual, "verified": not residual,
            "mapping": str(mapping_path) if mapping_path else None}
