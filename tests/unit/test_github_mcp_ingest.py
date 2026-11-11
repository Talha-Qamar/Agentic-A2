"""B1: the GitHub-MCP ingestion walk yields the same documents as the local loader (server replaced by a fake tool
that answers exactly like get_file_contents: directory -> list of entries, file -> base64 content object)."""
import asyncio
import base64
import json
from pathlib import Path

from rag.ingest.github_mcp import fetch_tree
from rag.ingest.loaders import load_repo_files

ROOT = Path(__file__).resolve().parents[2]
BASE = "data/personas/ai_ml_engineer/repos"


class FakeGet:
    async def ainvoke(self, args):
        p = ROOT / args["path"]
        if p.is_dir():
            return json.dumps([{"name": c.name, "path": str(c.relative_to(ROOT)), "type": "dir" if c.is_dir() else "file"} for c in p.iterdir()])
        return json.dumps({"type": "file", "path": args["path"], "encoding": "base64", "content": base64.b64encode(p.read_bytes()).decode()})


def test_walk_matches_local_loader():
    repo = sorted(d.name for d in (ROOT / BASE).iterdir() if d.is_dir())[0]
    files = asyncio.run(fetch_tree("o", "r", f"{BASE}/{repo}", get=FakeGet()))
    assert any(k.lower() == "readme.md" for k in files)
    local = {str(f.relative_to(ROOT / BASE / repo)): f.read_text() for f in (ROOT / BASE / repo).rglob("*") if f.is_file() and f.name in files or str(f.relative_to(ROOT / BASE / repo)) in files}
    a = load_repo_files("ai_ml_engineer", repo, files, None, f"repos/{repo}")
    b = load_repo_files("ai_ml_engineer", repo, local, None, f"repos/{repo}")
    assert [(d.type, d.source, d.text) for d in a] == [(d.type, d.source, d.text) for d in b]
