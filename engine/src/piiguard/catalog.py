"""Model catalogue: one recommended model per memory tier.

`measured` is filled from bench/results.json (see `piiguard bench`); the
settings window shows these numbers so the recommendation is never a guess.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

CATALOG = [
    # tier_gb: the smallest Mac this model is recommended for.
    {"id": "mlx-community/Qwen3.5-2B-MLX-4bit", "family": "Qwen 3.5", "params": "2B", "disk_gb": 1.8, "tier_gb": 8, "license": "Apache-2.0"},
    {"id": "mlx-community/gemma-4-e2b-it-4bit", "family": "Gemma 4", "params": "E2B", "disk_gb": 3.6, "tier_gb": 8, "license": "Apache-2.0 (upstream)"},
    {"id": "mlx-community/Qwen3.5-4B-MLX-4bit", "family": "Qwen 3.5", "params": "4B", "disk_gb": 3.1, "tier_gb": 16, "license": "Apache-2.0"},
    {"id": "mlx-community/gemma-4-e4b-it-4bit", "family": "Gemma 4", "params": "E4B", "disk_gb": 5.2, "tier_gb": 16, "license": "Apache-2.0 (upstream)"},
    {"id": "mlx-community/Qwen3.5-9B-6bit", "family": "Qwen 3.5", "params": "9B", "disk_gb": 8.2, "tier_gb": 24, "license": "Apache-2.0"},
    {"id": "mlx-community/gemma-4-12B-it-4bit", "family": "Gemma 4", "params": "12B", "disk_gb": 6.8, "tier_gb": 24, "license": "Apache-2.0 (upstream)"},
    {"id": "rapid-mlx/Qwen3.8-27B-4bit-MTP-MLX", "family": "Qwen 3.8", "params": "27B", "disk_gb": 16.3, "tier_gb": 32, "license": "Apache-2.0"},
    {"id": "mlx-community/gemma-4-26b-a4b-it-4bit", "family": "Gemma 4", "params": "26B-A4B", "disk_gb": 15.4, "tier_gb": 32, "license": "Apache-2.0"},
]
TIERS = (8, 16, 24, 32)
RESULTS = Path(__file__).parent / "bench_results.json"


def machine_ram_gb() -> int:
    try:
        b = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout)
        return round(b / 2**30)
    except Exception:
        return 0


def machine_tier(ram: int | None = None) -> int:
    ram = ram or machine_ram_gb()
    return max([t for t in TIERS if t <= ram] or [8])


def is_downloaded(model_id: str) -> bool:
    d = Path.home() / ".cache/huggingface/hub" / ("models--" + model_id.replace("/", "--")) / "snapshots"
    return d.is_dir() and any(any(s.glob("*.safetensors")) for s in d.iterdir())


def models() -> dict:
    measured = json.loads(RESULTS.read_text("utf-8")) if RESULTS.exists() else {}
    picks = measured.get("recommended", {})  # {"8": model_id, ...}
    ram = machine_ram_gb()
    tier = machine_tier(ram)
    rows = []
    for m in CATALOG:
        row = dict(m)
        row["downloaded"] = is_downloaded(m["id"])
        row["measured"] = measured.get("models", {}).get(m["id"])
        row["recommended_for"] = [int(t) for t, mid in picks.items() if mid == m["id"]]
        row["fits_this_mac"] = m["tier_gb"] <= tier
        rows.append(row)
    return {"ram_gb": ram, "tier_gb": tier, "recommended": picks.get(str(tier)),
            "measured_on": measured.get("measured_on"), "models": rows}
