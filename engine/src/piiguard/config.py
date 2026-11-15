"""Settings shared by the CLI and the menu bar app (one JSON file)."""
from __future__ import annotations

import json
import os
from pathlib import Path

APP_DIR = Path(os.environ.get("PIIGUARD_HOME") or
               Path.home() / "Library" / "Application Support" / "PII-guard-mac")
CONFIG_PATH = APP_DIR / "config.json"

# Words that look like names to a model but are not people.
DEFAULT_WHITELIST = [
    "行政", "各科", "小計", "患者", "病人", "病患", "家屬", "個案", "主治醫師", "住院醫師",
    "值班醫師", "專科護理師", "護理師", "護理長", "藥師", "醫檢師", "放射師", "看護", "照服員",
    "內科", "外科", "骨科", "家醫科", "耳鼻喉科", "神經內科", "身心內科", "復健科", "急診科",
    "胃腸內科", "心臟內科", "胸腔內科", "小兒科", "婦產科", "泌尿科", "皮膚科", "眼科", "牙科",
    "巴金森氏症", "阿茲海默症", "帕金森氏症", "庫欣氏症", "克隆氏症", "川崎氏症", "華佗", "南丁格爾",
]

DEFAULTS = {
    "model": None,
    "mode": "keep_surname",
    "mask_char": "○",
    "categories": {"person": True, "tw_id": False, "phone": False, "email": False, "mrn": False},
    "custom_patterns": [],          # [{"name": "員工編號", "pattern": "E\\d{5}"}]
    "use_default_whitelist": True,
    "whitelist": [],                # never mask these
    "blacklist": [],                # always mask these (treated as person names)
    "review": True,                 # show the review list before writing
    "write_mapping": False,         # also write an original→replacement table
    "scrub_metadata": True,
    "output_suffix": "_去識別",
}


def load() -> dict:
    cfg = json.loads(json.dumps(DEFAULTS))
    if CONFIG_PATH.exists():
        try:
            user = json.loads(CONFIG_PATH.read_text("utf-8"))
        except json.JSONDecodeError:
            user = {}
        for k, v in user.items():
            if k == "categories" and isinstance(v, dict):
                cfg["categories"].update(v)
            elif k in cfg:
                cfg[k] = v
    return cfg


def save(cfg: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")


def whitelist(cfg: dict) -> set[str]:
    wl = set(cfg.get("whitelist") or [])
    if cfg.get("use_default_whitelist", True):
        wl |= set(DEFAULT_WHITELIST)
    return wl
