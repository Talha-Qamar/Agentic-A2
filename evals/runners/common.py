"""Shared evaluation helpers: dev-set loading, gold mapping, metrics, result writing with provenance."""
from __future__ import annotations

import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "evals" / "results"
DATASETS = ROOT / "evals" / "datasets"


def load_dev(persona: str | None = None, limit_per_persona: int | None = None, seed_sample: bool = True) -> list[dict]:
    rows = [json.loads(line) for line in open(DATASETS / "dev_set.jsonl")]
    if persona:
        rows = [r for r in rows if r["persona"] == persona]
    if limit_per_persona:
        out = []
        for p in sorted({r["persona"] for r in rows}):
            sub = [r for r in rows if r["persona"] == p]
            out += sub[:limit_per_persona]
        rows = out
    return rows


class GoldMapper:
    """Maps a retrieved chunk to the portfolio project it evidences (evaluation-side only)."""

    def __init__(self, persona: str):
        m = json.loads((DATASETS / "gold" / f"{persona}_corpus_manifest.json").read_text())
        self.path_to_project = {d["path"]: d["project"] for d in m["documents"] if d["project"]}
        self.client_to_project = {p["client"].lower(): p["id"] for p in m["projects"]}

    def project_of(self, ev: dict) -> str | None:
        if ev.get("project"):
            return ev["project"]
        src = ev.get("source", "")
        if src in self.path_to_project:
            return self.path_to_project[src]
        if ev.get("type") == "proposal" and ev.get("cited_projects"):
            return ev["cited_projects"][0]
        if ev.get("type") == "review" and "#rev-" in src:
            pid = src.split("#rev-")[1]
            return pid if not pid.startswith("misc") else None
        low = ev.get("text", "").lower()
        for client, pid in self.client_to_project.items():
            if client in low:
                return pid
        item = ev.get("item_id") or ""
        if item.startswith("repo:"):
            for path, pid in self.path_to_project.items():
                if path.startswith(f"repos/{item[5:]}/"):
                    return pid
        return None

    def ranked_projects(self, evidence: list[dict]) -> list[str]:
        seen, out = set(), []
        for e in evidence:
            p = self.project_of(e)
            if p and p not in seen:
                seen.add(p)
                out.append(p)
        return out


def recall_at(ranked: list[str], gold: dict, k: int) -> float:
    if not gold:
        return float("nan")
    return len(set(ranked[:k]) & set(gold)) / len(gold)


def capped_recall_at(ranked: list[str], gold: dict, k: int) -> float:
    if not gold:
        return float("nan")
    return len(set(ranked[:k]) & set(gold)) / min(k, len(gold))


def mrr(ranked: list[str], gold: dict) -> float:
    for i, p in enumerate(ranked):
        if p in gold:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at(ranked: list[str], gold: dict, k: int) -> float:
    if not gold:
        return float("nan")
    dcg = sum((2 ** gold.get(p, 0) - 1) / math.log2(i + 2) for i, p in enumerate(ranked[:k]))
    ideal = sorted(gold.values(), reverse=True)[:k]
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def pct(xs: list[float], q: float) -> float:
    xs = [x for x in xs if x == x]
    return float(np.percentile(xs, q)) if xs else float("nan")


def mean(xs: list[float]) -> float:
    xs = [x for x in xs if x == x]
    return float(np.mean(xs)) if xs else float("nan")


def provenance(extra: dict | None = None) -> dict:
    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        sha = "unknown"
    return {"git_sha": sha, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "host": platform.node(),
            "machine": platform.machine(), "python": platform.python_version(),
            "profile": os.environ.get("GIGBID_PROFILE", "open"), **(extra or {})}


def write_result(name: str, payload: dict) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    p = RESULTS / name
    p.write_text(json.dumps(payload, indent=1, default=float))
    return p


def job_text(job: dict) -> str:
    return f"{job['title']}\n\n{job['description']}"
