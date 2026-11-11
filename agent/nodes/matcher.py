"""Fit Matcher: requirement decomposition -> Portfolio MCP (match_requirements) -> cross-encoder grading.

Runs in parallel with the Job Analyst, so it extracts requirements deterministically from the (quarantined) post.
Support per requirement = best cross-encoder probability over its top evidence; fit = coverage-weighted score.
"""
from __future__ import annotations

import math

from agent import settings
from agent.handoffs import FitReport, RequirementMatch
from agent.nodes.runtime import Deps, node
from rag.requirements import extract_requirements


def _sig(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def grade(requirement: str, evidence: list[dict]) -> float:
    if not evidence:
        return 0.0
    try:
        from rag.embed import get_reranker
        rr = get_reranker()
        scores = rr.score(requirement, [e["text"][:1500] for e in evidence[:3]])
        return max((_sig(s) if hasattr(rr, "m") else s) for s in scores)
    except Exception:  # noqa: BLE001
        return max(min(1.0, e.get("score", 0) * 20) for e in evidence[:3])


def fit_from(reqs: list[dict], per: dict[str, list[dict]], unsupported: list[str]) -> FitReport:
    strong_t = settings.get("thresholds.support_strong", 0.5)
    partial_t = settings.get("thresholds.support_partial", 0.15)
    matches, probs = [], []
    for r in reqs:
        ev = [] if r["id"] in unsupported else per.get(r["id"], [])
        p = grade(r["text"], ev)
        probs.append(p)
        sup = "strong" if p >= strong_t else ("partial" if p >= partial_t else "none")
        matches.append(RequirementMatch(requirement_id=r["id"], requirement=r["text"], evidence_ids=[e["evidence_id"] for e in ev[:3]],
                                        support=sup, score=round(p, 4)))
    n = max(1, len(matches))
    coverage = sum(1.0 if m.support == "strong" else 0.5 if m.support == "partial" else 0 for m in matches) / n
    fit = 0.75 * coverage + 0.25 * (sum(probs) / n)
    return FitReport(fit_score=round(fit, 4), coverage=round(coverage, 4), matches=matches,
                     strengths=[m.requirement for m in matches if m.support == "strong"][:4],
                     gaps=[m.requirement for m in matches if m.support == "none"][:4],
                     reasons=[f"{sum(m.support == 'strong' for m in matches)}/{n} requirements strongly evidenced, "
                              f"{sum(m.support == 'partial' for m in matches)} partly"])


@node("matcher", retries=1)
async def matcher(state: dict, deps: Deps) -> dict:
    text = state.get("job_clean_text") or f"{state['job']['title']}\n\n{state['job']['description']}"
    reqs = extract_requirements(text)
    out = await deps.call("matcher", "match_requirements", {"job_text": text[:12000],
                                                            "requirements": [{"id": r["id"], "text": r["text"][:400]} for r in reqs], "k": 5})
    per = out.get("per_requirement", {})
    fit = fit_from(reqs, per, out.get("unsupported_requirements", []))
    evidence = []
    seen = set()
    for lst in per.values():
        for e in lst[:3]:
            if e["evidence_id"] not in seen:
                seen.add(e["evidence_id"])
                evidence.append(e)
    return {"fit": fit.model_dump() | {"variant": out.get("variant"), "requirements": reqs}, "evidence": evidence}
