"""Ingest repository READMEs and code through a third-party GitHub MCP server (B1).

Server: `@modelcontextprotocol/server-github` (MCP reference server, published by the modelcontextprotocol npm org),
launched over stdio. GitHub's own `github-mcp-server` (Go binary / ghcr.io image) exposes the same
`get_file_contents` tool and can be selected with GITHUB_MCP_COMMAND. Trust rationale and permissions: docs/SECURITY.md
(read-only use; a fine-grained PAT with public-repo read scope is enough; unauthenticated reads work for public repos).

    python -m rag.ingest.github_mcp --owner Talha-Qamar --repo Agentic-A2 \
        --path data/personas/ai_ml_engineer/repos --persona ai_ml_engineer --out var/github_ingest/ai_ml_engineer
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shlex
from pathlib import Path

from rag.ingest.loaders import CODE_EXT, load_repo_files


def server_config() -> dict:
    cmd = shlex.split(os.environ.get("GITHUB_MCP_COMMAND", "npx -y @modelcontextprotocol/server-github@2025.4.8"))
    return {"github": {"transport": "stdio", "command": cmd[0], "args": cmd[1:],
                       "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ.get("GITHUB_TOKEN", ""), "PATH": os.environ.get("PATH", "")}}}


def _parse(out):
    if isinstance(out, tuple):
        out = out[0]
    if isinstance(out, list):
        out = "".join(b.get("text", "") if isinstance(b, dict) else getattr(b, "text", str(b)) for b in out)
    try:
        return json.loads(out)
    except (TypeError, json.JSONDecodeError):
        return out


async def fetch_tree(owner: str, repo: str, path: str, branch: str = "main", max_files: int = 300, get=None) -> dict[str, str]:
    """Walk `path` with get_file_contents and return {relative_path: text} for READMEs and code files."""
    if get is None:
        from langchain_mcp_adapters.client import MultiServerMCPClient
        client = MultiServerMCPClient(server_config())
        tools = {t.name: t for t in await client.get_tools()}
        get = tools["get_file_contents"]
    files: dict[str, str] = {}
    stack = [path]
    while stack and len(files) < max_files:
        p = stack.pop()
        res = _parse(await get.ainvoke({"owner": owner, "repo": repo, "path": p, "branch": branch}))
        if isinstance(res, list):
            for e in res:
                if e.get("type") == "dir":
                    stack.append(e["path"])
                elif e.get("type") == "file" and (e["name"].lower() == "readme.md" or Path(e["name"]).suffix in CODE_EXT
                                                   or e["name"] in ("requirements.txt", "package.json")):
                    stack.append(e["path"])
        elif isinstance(res, dict) and res.get("type") == "file":
            import base64
            txt = base64.b64decode(res["content"]).decode("utf-8", "ignore") if res.get("encoding") == "base64" else res.get("content", "")
            files[res["path"][len(path):].lstrip("/")] = txt
    return files


def ingest(owner: str, repo: str, path: str, persona: str, out: Path | None = None, branch: str = "main"):
    files = asyncio.run(fetch_tree(owner, repo, path, branch))
    by_repo: dict[str, dict[str, str]] = {}
    for rel, txt in files.items():
        name, _, sub = rel.partition("/")
        by_repo.setdefault(name, {})[sub] = txt
    docs = []
    for name, fs in by_repo.items():
        docs += load_repo_files(persona, name, fs, None, source_prefix=f"repos/{name}")
        if out:
            for sub, txt in fs.items():
                f = Path(out) / name / sub
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(txt)
    return docs


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--path", default="")
    ap.add_argument("--persona", default="ai_ml_engineer")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    d = ingest(a.owner, a.repo, a.path, a.persona, Path(a.out) if a.out else None, a.branch)
    print(f"ingested {len(d)} documents from {a.owner}/{a.repo}/{a.path} via GitHub MCP")
