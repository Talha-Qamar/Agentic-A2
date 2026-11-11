"""Extension X3 - Portfolio builder: which case study should the freelancer write next?

Inputs: the freelancer's analysed jobs (requirements and how well each was evidenced) and their portfolio corpus.
1. Gap mining: requirements graded `none`/`partial` on jobs the freelancer had to skip or watch, grouped by skill,
   weighted by the job budget they would have unlocked.
2. Hidden strengths: skills that appear in repository code/READMEs but in no case study, CV line or review - the
   freelancer has done the work but never wrote it up (e.g. Celery used in a repo whose README says nothing).
3. Ranking: score = jobs needing the skill x budget weight x (2 if hidden evidence exists else 1). Suggestions with
   hidden evidence come with a draft outline built ONLY from the repo's own text (no invented facts).
"""
from __future__ import annotations

import math
import re
from collections import defaultdict

from rag.index.graph import canon
from rag.ingest.loaders import extract_skills

GENERIC = {"bash", "json", "yaml", "make", "npm", "pip", "python", "sql", "typescript", "javascript", "api", "rest api", "llm", "agents", "performance", "evaluation", "caching"}


def hidden_strengths(chunks: list[dict]) -> dict[str, list[dict]]:
    prose = set()
    repos = {(c.get("repo") or "").lower() for c in chunks}
    for c in chunks:
        if c["type"] in ("case_study", "cv", "review"):
            prose |= {canon(s) for s in c.get("skills", [])} | {canon(s) for s in extract_skills(c.get("text", ""))}
    out: dict[str, list[dict]] = defaultdict(list)
    for c in chunks:
        if c["type"] in ("code", "readme"):
            for s in c.get("skills", []):
                s = canon(s)
                if s not in prose and s not in GENERIC and len(s) > 2 and s not in repos and s not in ("service", "regex"):
                    out[s].append({"repo": c.get("repo"), "source": c["source"], "project": c.get("project")})
    return out


def mine_gaps(job_summaries: list[dict]) -> dict[str, dict]:
    gaps: dict[str, dict] = defaultdict(lambda: {"jobs": set(), "budget": 0.0, "examples": []})
    for j in job_summaries:
        action = (j.get("decision") or {}).get("action")
        if action not in ("skip", "watch"):
            continue
        if (j.get("risk") or {}).get("scam_score", 0) >= 0.5:
            continue
        budget = (j.get("job") or {}).get("budget_max") or 0
        for m in (j.get("fit") or {}).get("matches", []):
            if m["support"] == "strong":
                continue
            for s in {canon(x) for x in extract_skills(m["requirement"]) or []}:
                if s in GENERIC:
                    continue
                g = gaps[s]
                g["jobs"].add(j.get("job_id"))
                g["budget"] += float(budget)
                if len(g["examples"]) < 3:
                    g["examples"].append(m["requirement"])
    return gaps


def suggest(job_summaries: list[dict], chunks: list[dict], top: int = 5) -> list[dict]:
    gaps = mine_gaps(job_summaries)
    hidden = hidden_strengths(chunks)
    out = []
    for skill, g in gaps.items():
        hid = hidden.get(skill, [])
        score = len(g["jobs"]) * (1 + math.log1p(g["budget"] / 500)) * (2.0 if hid else 1.0)
        out.append({"skill": skill, "score": round(score, 2), "jobs_affected": len(g["jobs"]), "budget_at_stake": round(g["budget"], 0),
                    "hidden_evidence": hid[:3], "example_requirements": g["examples"],
                    "action": (f"Write a case study about your {skill} work in {hid[0]['repo']} - the code proves it, no prose mentions it."
                               if hid else f"You have no evidence for {skill}; consider a small project or drop it from searches.")})
    for skill, hid in hidden.items():
        if skill not in gaps:
            out.append({"skill": skill, "score": 0.5, "jobs_affected": 0, "budget_at_stake": 0, "hidden_evidence": hid[:3], "example_requirements": [],
                        "action": f"Hidden strength: {skill} appears only in code ({hid[0]['repo']}). A short write-up makes it findable."})
    return sorted(out, key=lambda x: -x["score"])[:top]


def outline_from_repo(skill: str, chunks: list[dict], repo: str) -> str:
    """A case-study draft assembled only from the repo's own README/code text (facts the freelancer already has)."""
    rc = [c for c in chunks if c.get("repo") == repo]
    readme = next((c["text"] for c in rc if c["type"] == "readme"), "")
    first = re.sub(r"<!--.*?-->|#.*\n", "", readme).strip().split("\n")[0][:300]
    files = sorted({c["source"].split("/", 2)[-1] for c in rc if c["type"] == "code" and skill in [s.lower() for s in c.get("skills", [])]})
    return (f"# {repo}: {skill} in production\n\n{first}\n\nThis project used {skill} "
            f"(see {', '.join(files[:3]) or 'the repository'}). "
            "[Add: the problem it solved, what you measured, the result.]")
