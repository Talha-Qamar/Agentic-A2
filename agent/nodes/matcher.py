"""Fit Matcher: requirement decomposition -> Portfolio MCP (match_requirements) -> cross-encoder grading.

Runs in parallel with the Job Analyst, so it extracts requirements deterministically from the (quarantined) post.
Support per requirement = max(skill-graph support, best cross-encoder probability) over its top evidence;
fit = coverage-weighted score. Thresholds are set on the dev split (evals/results/fit_calibration.json).
"""
from __future__ import annotations

import math

from agent import settings
from agent.handoffs import FitReport, RequirementMatch
from agent.nodes.runtime import Deps, node
from rag.requirements import extract_requirements


def _sig(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def skill_support(requirement: str, evidence: list[dict]) -> float:
    """Graph-style support: share of the requirement's skills (canonicalised, incl. implied phrasings) that occur in
    the skills or text of one of its top evidence items. Covers code/README evidence that a prose-trained
    cross-encoder scores near zero (the cross-encoder also lowered retrieval recall in the ablation)."""
    from rag.index.graph import canon
    from rag.ingest.loaders import extract_skills
    rs = {canon(x) for x in extract_skills(requirement)} - GENERIC
    if not rs:
        return 0.0
    best = 0.0
    for e in evidence[:3]:
        es = {canon(x) for x in (e.get("skills") or [])} | {canon(x) for x in extract_skills(e.get("text", ""))}
        best = max(best, len(rs & es) / len(rs))
    return 0.8 if best >= 0.999 else 0.45 if best >= 0.5 else 0.25 if best > 0 else 0.0


GENERIC = {"api", "rest api", "json"}


PROOF_TYPES = {"case_study", "readme", "code", "cv", "review"}


def grade(requirement: str, evidence: list[dict]) -> float:
    """Past proposals are bids, not proof: they often repeat a job's wording ("shipped Flutter apps") without the
    freelancer having done it, so only case studies, repos, CV lines and client reviews can support a requirement."""
    evidence = [e for e in evidence if e.get("type", "case_study") in PROOF_TYPES]
    if not evidence:
        return 0.0
    return max(skill_support(requirement, evidence), cross_encoder_support(requirement, evidence))


def cross_encoder_support(requirement: str, evidence: list[dict]) -> float:
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
