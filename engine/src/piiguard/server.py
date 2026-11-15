"""Run one Rapid-MLX server process per loaded model.

Load   = start the process (first run downloads the weights).
Unload = terminate the process, which returns all memory to the system.
The server only listens on 127.0.0.1 with a random port and bearer token.
"""
from __future__ import annotations

import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .config import APP_DIR

STATE = APP_DIR / "server.json"
LOG = APP_DIR / "server.log"


def _alive(pid: int) -> bool:
    _reap(pid)
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _reap(pid: int) -> None:
    """Collect the exit status when the server is our own child, so a finished
    process is not mistaken for a live one (a zombie still answers kill 0)."""
    try:
        os.waitpid(pid, os.WNOHANG)
    except OSError:  # not our child, or already collected
        pass


def _read() -> dict | None:
    if not STATE.exists():
        return None
    try:
        st = json.loads(STATE.read_text())
    except json.JSONDecodeError:
        st = None
    if not st or not _alive(st.get("pid", -1)):
        STATE.unlink(missing_ok=True)
        return None
    return st


def _get(st: dict, path: str, timeout: float = 2.0):
    req = urllib.request.Request(f"http://127.0.0.1:{st['port']}{path}",
                                 headers={"Authorization": f"Bearer {st['key']}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def status() -> dict:
    st = _read()
    if not st:
        return {"state": "stopped", "model": None}
    try:
        code, _ = _get(st, "/health/ready")
        state = "ready" if code == 200 else "loading"
    except (urllib.error.URLError, OSError, TimeoutError):
        state = "loading"
    return {"state": state, "model": st["model"], "port": st["port"], "pid": st["pid"],
            "since": st["started"]}


def connection() -> dict | None:
    """Port and token for the detector; None when no server is running."""
    return _read()


def _signal(pid: int, sig: int) -> None:
    try:
        os.killpg(pid, sig)
    except (ProcessLookupError, PermissionError):
        pass  # already gone


def stop() -> dict:
    st = _read()
    if st:
        pid = st["pid"]
        _signal(pid, signal.SIGTERM)
        for _ in range(50):
            if not _alive(pid):  # also reaps a finished child
                break
            time.sleep(0.2)
        else:
            _signal(pid, signal.SIGKILL)
            time.sleep(0.5)
            _reap(pid)
        STATE.unlink(missing_ok=True)
    return {"state": "stopped", "model": None}


def start(model: str) -> dict:
    st = _read()
    if st and st["model"] == model:
        return status()
    if st:
        stop()
    APP_DIR.mkdir(parents=True, exist_ok=True)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    key = secrets.token_hex(16)
    exe = Path(sys.executable).parent / "rapid-mlx"
    cmd = [str(exe), "serve", model, "--host", "127.0.0.1", "--port", str(port),
           "--api-key", key, "--max-num-seqs", "1", "--cache-memory-mb", "512"]
    env = dict(os.environ, HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1")
    with open(LOG, "wb") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True, env=env)
    STATE.write_text(json.dumps({"pid": proc.pid, "port": port, "key": key, "model": model,
                                 "started": int(time.time())}))
    STATE.chmod(0o600)
    return status()


def wait_ready(timeout: float = 3600) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        st = status()
        if st["state"] != "loading":
            return st
        time.sleep(1)
    return status()


def log_tail(n: int = 5) -> str:
    if not LOG.exists():
        return ""
    return "\n".join(LOG.read_text("utf-8", "replace").splitlines()[-n:])
