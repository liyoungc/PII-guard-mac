"""Measure every catalogue model on the synthetic corpus.

Usage: .venv/bin/python bench/run_bench.py MODEL_ID [MODEL_ID ...]
Results are merged into engine/src/piiguard/bench_results.json. Recall is the
number that matters: a missed name is a privacy failure, a false alarm is one
extra tick in the review list.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

from piiguard import catalog, detect, server
from piiguard.documents import Unit

HERE = Path(__file__).parent
CORPUS = [json.loads(l) for l in (HERE / "corpus.jsonl").read_text("utf-8").splitlines() if l.strip()]


def rss_gb(pid: int) -> float:
    out = subprocess.run(["footprint", str(pid)], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if "phys_footprint:" in line and "peak" not in line:
            num, unit = line.split(":")[1].split()[:2]
            return round(float(num) / (1024 if unit == "MB" else 1), 2)
    return 0.0


def bench(model: str) -> dict:
    server.start(model)
    t0 = time.time()
    st = server.wait_ready(7200)
    if st["state"] != "ready":
        return {"error": "server did not become ready", "log": server.log_tail(8)}
    load_s = round(time.time() - t0, 1)
    conn = server.connection()
    tp = fp = fn = errors = 0
    misses, extras = [], []
    t1 = time.time()
    chars = 0
    for item in CORPUS:
        chars += len(item["text"])
        try:
            got, _ = detect.find_names([Unit(item["text"])], conn)
        except detect.ModelError:
            errors += 1
            got = []
        gold = set(item["names"])
        got = set(got)
        tp += len(gold & got); fn += len(gold - got); fp += len(got - gold)
        misses += [f"{item['id']}:{n}" for n in gold - got]
        extras += [f"{item['id']}:{n}" for n in got - gold]
    secs = time.time() - t1
    mem = rss_gb(conn["pid"])
    server.stop()
    return {"recall": round(tp / (tp + fn), 3), "precision": round(tp / max(tp + fp, 1), 3),
            "missed": misses, "false_alarms": extras, "errors": errors,
            "chars_per_sec": round(chars / secs), "memory_gb": mem, "load_seconds": load_s,
            "gold_names": tp + fn, "documents": len(CORPUS)}


if __name__ == "__main__":
    path = catalog.RESULTS
    data = json.loads(path.read_text("utf-8")) if path.exists() else {"models": {}}
    for m in sys.argv[1:]:
        print("==>", m, flush=True)
        data["models"][m] = bench(m)
        print(json.dumps(data["models"][m], ensure_ascii=False, indent=1), flush=True)
        data["measured_on"] = f"Apple {subprocess.run(['sysctl','-n','machdep.cpu.brand_string'],capture_output=True,text=True).stdout.strip().replace('Apple ','')}, {catalog.machine_ram_gb()} GB, rapid-mlx 1.0.3, {time.strftime('%Y-%m-%d')}"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
