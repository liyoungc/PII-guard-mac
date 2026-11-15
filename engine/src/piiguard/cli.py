"""piiguard — command line interface. Every command prints one JSON object."""
from __future__ import annotations

import argparse
import json
import sys

from . import catalog, config as cfgmod, detect, masking, pipeline, server
from .documents import SUPPORTED_EXT, UnsupportedFormat


def _out(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _progress(i: int, n: int) -> None:
    print(json.dumps({"progress": i, "total": n}), file=sys.stderr, flush=True)


def _cfg(args) -> dict:
    cfg = cfgmod.load()
    if getattr(args, "mode", None):
        cfg["mode"] = args.mode
    if getattr(args, "mask_char", None):
        cfg["mask_char"] = args.mask_char
    if getattr(args, "mapping", False):
        cfg["write_mapping"] = True
    return cfg


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="piiguard", description="本機文件人名去識別化（Rapid-MLX）")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("models", help="列出各記憶體級距的建議模型")
    sub.add_parser("info", help="支援格式、遮蔽模式、類別")

    sv = sub.add_parser("server", help="載入／卸載模型")
    sv.add_argument("action", choices=["start", "stop", "status"])
    sv.add_argument("--model")
    sv.add_argument("--wait", action="store_true", help="等到模型就緒才返回")

    def common(sp):
        sp.add_argument("file")
        sp.add_argument("--mode", choices=masking.MODES)
        sp.add_argument("--mask-char")

    sc = sub.add_parser("scan", help="找出要遮蔽的項目（不寫檔）")
    common(sc)
    ap = sub.add_parser("apply", help="依確認過的清單寫出去識別檔")
    common(ap)
    ap.add_argument("--decisions", required=True, help="scan 輸出（可編輯）的 JSON 檔，- 代表 stdin")
    ap.add_argument("--out")
    ap.add_argument("--mapping", action="store_true", help="同時輸出對照表")
    rn = sub.add_parser("run", help="scan 後全部接受並直接寫檔")
    common(rn)
    rn.add_argument("--out")
    rn.add_argument("--mapping", action="store_true")

    pv = sub.add_parser("preview", help="重新計算清單的取代結果（stdin: {entities}）")
    pv.add_argument("--mode", choices=masking.MODES)
    pv.add_argument("--mask-char")

    cf = sub.add_parser("config", help="顯示設定")
    cf.add_argument("action", choices=["show", "path"], nargs="?", default="show")

    args = p.parse_args(argv)
    try:
        if args.cmd == "models":
            _out(catalog.models())
        elif args.cmd == "info":
            _out({"formats": SUPPORTED_EXT, "modes": masking.MODE_LABELS,
                  "categories": detect.CATEGORY_LABELS,
                  "default_whitelist": cfgmod.DEFAULT_WHITELIST})
        elif args.cmd == "server":
            if args.action == "start":
                model = args.model or cfgmod.load().get("model") or catalog.models()["recommended"]
                if not model:
                    raise ValueError("請用 --model 指定模型（piiguard models 可列出建議）。")
                st = server.start(model)
                _out(server.wait_ready() if args.wait else st)
            elif args.action == "stop":
                _out(server.stop())
            else:
                _out({**server.status(), "log": server.log_tail(3)})
        elif args.cmd == "scan":
            _out(pipeline.scan(args.file, _cfg(args), _progress))
        elif args.cmd == "apply":
            raw = sys.stdin.read() if args.decisions == "-" else open(args.decisions, encoding="utf-8").read()
            _out(pipeline.apply(args.file, json.loads(raw)["entities"], _cfg(args), args.out))
        elif args.cmd == "run":
            cfg = _cfg(args)
            found = pipeline.scan(args.file, cfg, _progress)
            res = pipeline.apply(args.file, found["entities"], cfg, args.out)
            _out({**res, "entities": found["entities"], "whitelisted": found["whitelisted"]})
        elif args.cmd == "preview":
            _out({"entities": pipeline.preview(json.loads(sys.stdin.read())["entities"], _cfg(args))})
        elif args.cmd == "config":
            _out({"path": str(cfgmod.CONFIG_PATH)} if args.action == "path" else cfgmod.load())
    except (UnsupportedFormat, detect.ModelError, ValueError, FileNotFoundError) as e:
        _out({"error": str(e)})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
