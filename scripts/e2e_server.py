"""Full stack for Playwright: GigSim + MCP servers + API (serving the built web app) on :8000, deterministic stub model.
Used by apps/web/playwright.config.ts and CI. Never used for reported results."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_stack  # noqa: E402

ENV = {"GIGBID_PROFILE": "stub", "GIGBID_EMBEDDER": os.environ.get("GIGBID_EMBEDDER", "hash"),
       "GIGBID_RERANKER": os.environ.get("GIGBID_RERANKER", "overlap"), "GIGSIM_ERROR_RATE": "0", "GITHUB_MCP_COMMAND": "/bin/false",
       "GIGBID_FIT_BID": "0", "GIGBID_FIT_WATCH": "0", "GIGSIM_DB": str(ROOT / "var" / "e2e_gigsim.db"),
       "DATABASE_URL": os.environ.get("DATABASE_URL", "postgresql://gigbid:gigbid@localhost:5432/gigbid")}

if __name__ == "__main__":
    for f in (ROOT / "var").glob("e2e_gigsim.db*"):
        f.unlink()
    os.environ.update(ENV)
    ps = run_stack.start(ENV)
    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "apps.api.main:app", "--port", "8000", "--log-level", "warning"],
                           cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)})
    try:
        while api.poll() is None:
            time.sleep(1)
    finally:
        api.terminate()
        run_stack.stop(ps)
