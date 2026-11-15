"""Rewrite the measured-model table between the BENCH markers in both READMEs."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
data = json.loads((ROOT / "engine/src/piiguard/bench_results.json").read_text("utf-8"))
from piiguard.catalog import CATALOG  # noqa: E402

picks: dict[str, list[str]] = {}
for t, mid in data.get("recommended", {}).items():
    picks.setdefault(mid, []).append(t)


def table(zh: bool) -> str:
    head = ("| 最低記憶體 | 模型 | 召回率 | 精確率 | 速度（字／秒） | 記憶體 | 下載大小 | 建議用於 |" if zh else
            "| Min RAM | Model | Recall | Precision | Speed (chars/s) | Memory | Download | Pick for |")
    rows = [head, "|---|---|---|---|---|---|---|---|"]
    for m in CATALOG:
        r = data["models"].get(m["id"])
        if not r or "recall" not in r:
            cells = ["—"] * 4 if not r else ["error"] * 4
        else:
            cells = [f"{r['recall']:.1%}", f"{r['precision']:.1%}", str(r["chars_per_sec"]), f"{r['memory_gb']} GB"]
        pick = ("✅ " + "、".join(picks[m["id"]]) + " GB") if m["id"] in picks else ""
        rows.append(f"| {m['tier_gb']} GB | `{m['id']}` | " + " | ".join(cells) + f" | {m['disk_gb']} GB | {pick} |")
    note = (f"\n量測環境：{data.get('measured_on')}。語料：`bench/corpus.jsonl`（20 篇合成文件、49 個人名）。"
            if zh else
            f"\nMeasured on: {data.get('measured_on')}. Corpus: `bench/corpus.jsonl` (20 synthetic documents, 49 names).")
    return "\n".join(rows) + "\n" + note


for name, zh in (("README.md", False), ("README.zh-TW.md", True)):
    p = ROOT / name
    s = p.read_text("utf-8")
    s = re.sub(r"<!-- BENCH -->.*?<!-- /BENCH -->", f"<!-- BENCH -->\n{table(zh)}\n<!-- /BENCH -->", s, flags=re.S)
    p.write_text(s, "utf-8")
    print("updated", name)
