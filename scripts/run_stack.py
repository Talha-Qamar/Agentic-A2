"""Start GigSim + the three GigBid MCP servers as local processes (dev, tests, evaluation harness).

    python scripts/run_stack.py            # foreground; Ctrl+C stops all
Ports: GigSim 8100, portfolio 8201, marketplace 8202, workspace 8203 (override with env).
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def procs(env: dict) -> list[tuple[str, list[str], str]]:
    return [
        ("gigsim", [PY, "-m", "uvicorn", "gigsim.app:app", "--port", env.get("GIGSIM_PORT", "8100"), "--log-level", "warning"],
         f"http://localhost:{env.get('GIGSIM_PORT', '8100')}/health"),
        ("portfolio", [PY, "-m", "mcp_servers.portfolio.server", "--transport", "http", "--port", "8201"], "http://localhost:8201/mcp"),
        ("marketplace", [PY, "-m", "mcp_servers.marketplace.server", "--port", "8202"], "http://localhost:8202/mcp"),
        ("workspace", [PY, "-m", "mcp_servers.workspace.server", "--port", "8203"], "http://localhost:8203/mcp"),
    ]


def start(env: dict | None = None, log_dir: Path | None = None) -> list[subprocess.Popen]:
    env = {**os.environ, "PYTHONPATH": str(ROOT), **(env or {})}
    log_dir = log_dir or ROOT / "var" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for name, cmd, url in procs(env):
        p = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=open(log_dir / f"{name}.log", "w"), stderr=subprocess.STDOUT)
        out.append(p)
    for name, cmd, url in procs(env):
        for _ in range(120):
            try:
                r = httpx.get(url, timeout=1)
                if r.status_code < 500:
                    break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        else:
            raise RuntimeError(f"{name} did not start; see {log_dir}/{name}.log")
    return out


def stop(ps: list[subprocess.Popen]) -> None:
    for p in ps:
        p.send_signal(signal.SIGTERM)
    for p in ps:
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()


if __name__ == "__main__":
    ps = start()
    print("stack up: gigsim :8100, portfolio :8201, marketplace :8202, workspace :8203")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop(ps)
