"""Extension X3 evaluation: do the builder's suggestions actually unlock bids?

    python -m evals.runners.portfolio_builder_eval

Protocol (per persona, no LLM): run the Fit Matcher logic (deployed retrieval + cross-encoder grading) on the first
half of the dev set -> builder suggestions -> build case studies for the repos behind the top-3 suggestions with
the X3 pipeline (agent/case_study_builder.py: repo text only, claims verified against the code, no LLM here) to a copy of the portfolio -> re-run on the HELD-OUT second half -> compare requirement
coverage and fit for jobs that need the suggested skills, and how many jobs cross the bid threshold.
"""
from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

from agent import settings
from agent.case_study_builder import build, save
from agent.nodes.matcher import fit_from
from agent.portfolio_builder import suggest
from evals.runners.common import job_text, load_dev, mean, provenance, write_result
from rag.corpus import Corpus
from rag.ingest.loaders import extract_skills
from rag.requirements import extract_requirements
from rag.retriever import variant_class

ROOT = settings.ROOT


def analyse(retr, jobs):
    out = []
    for j in jobs:
        reqs = extract_requirements(job_text(j))
        res = retr.retrieve(job_text(j), requirements=reqs, k=8)
        fit = fit_from(reqs, {k: v for k, v in res.per_requirement.items()}, res.unsupported_requirements).model_dump()
        t = settings.get("thresholds")
        action = "bid" if fit["fit_score"] >= t["fit_bid"] else ("watch" if fit["fit_score"] >= t["fit_watch"] else "skip")
        out.append({"job_id": j["job_id"], "job": j, "fit": fit, "decision": {"action": action}, "risk": {"scam_score": 1.0 if j["labels"]["scam"] else 0}})
    return out


def llm_drafts() -> dict:
    """LLM case studies for every repo that has no case study (picked from the gold manifest, evaluation side only):
    how many claims the model makes, how many the code check supports, how many verification removes."""
    import json
    out = {}
    for persona in ("ai_ml_engineer", "fullstack_web_dev", "data_analyst"):
        m = json.loads((ROOT / "evals" / "datasets" / "gold" / f"{persona}_corpus_manifest.json").read_text())
        repos = sorted({d["path"].split("/")[1] for d in m["documents"] if d["type"] == "readme" and d["project"] in m["no_case_study"]})
        for repo in repos:
            rdir = ROOT / "data" / "personas" / persona / "repos" / repo
            files = {str(f.relative_to(rdir)): f.read_text(errors="ignore") for f in rdir.rglob("*") if f.is_file()}
            r = asyncio.run(build(repo, files, use_llm=True, source="eval-llm"))
            out[f"{persona}/{repo}"] = {"verification": r["verification"], "checks": r["checks"], "draft": r["draft"], "final": r["markdown"]}
            print(repo, r["verification"], flush=True)
    claims = sum(v["verification"]["claims"] for v in out.values())
    uns = sum(v["verification"]["unsupported"] for v in out.values())
    sup = sum(v["verification"]["supported"] for v in out.values())
    return {"repos": len(out), "claims": claims, "supported": sup, "unsupported_removed": uns,
            "unsupported_rate_before_verification": round(uns / claims, 4) if claims else None, "unsupported_rate_after": 0.0, "items": out}


def main() -> None:
    import sys
    cls = variant_class(settings.get("rag.variant"))
    report = {}
    for persona in ("ai_ml_engineer", "fullstack_web_dev", "data_analyst"):
        jobs = [j for j in load_dev(persona) if not j["labels"]["scam"]]
        train, test = jobs[: len(jobs) // 2], jobs[len(jobs) // 2:]
        base_retr = cls(persona)
        sugg = suggest(analyse(base_retr, train), base_retr.corpus.chunks, top=50)
        picks = [s for s in sugg if s["hidden_evidence"]][:3]
        tmp = Path(tempfile.mkdtemp())
        shutil.copytree(ROOT / "data" / "personas" / persona, tmp / persona)
        built = []
        for repo in dict.fromkeys(s["hidden_evidence"][0]["repo"] for s in picks):
            rdir = tmp / persona / "repos" / repo
            files = {str(f.relative_to(rdir)): f.read_text(errors="ignore") for f in rdir.rglob("*") if f.is_file()}
            r = asyncio.run(build(repo, files, use_llm=False, source="eval"))   # same pipeline as the UI, no model
            save(r, tmp / persona)
            built.append({"repo": repo, "verification": r["verification"], "skills": r["skills"]})
        new_corpus = Corpus.from_persona(persona, cls.chunking, None, cls.contextual, base=tmp / persona)
        new_retr = cls(persona, corpus=new_corpus)
        skills = {s["skill"] for s in picks}
        affected = [j for j in test if any(sk in skills for r in extract_requirements(job_text(j)) for sk in extract_skills(r["text"]))]
        before, after = analyse(base_retr, affected), analyse(new_retr, affected)
        report[persona] = {
            "suggestions": [{k: s[k] for k in ("skill", "score", "jobs_affected", "budget_at_stake", "action")} for s in sugg[:8]],
            "added_case_studies": [s["skill"] for s in picks], "built": built, "heldout_jobs_affected": len(affected),
            "coverage_before": round(mean([a["fit"]["coverage"] for a in before]), 4) if before else None,
            "coverage_after": round(mean([a["fit"]["coverage"] for a in after]), 4) if after else None,
            "fit_before": round(mean([a["fit"]["fit_score"] for a in before]), 4) if before else None,
            "fit_after": round(mean([a["fit"]["fit_score"] for a in after]), 4) if after else None,
            "bids_before": sum(a["decision"]["action"] == "bid" for a in before), "bids_after": sum(a["decision"]["action"] == "bid" for a in after),
            "gold_bid_among_affected": sum(j["labels"]["gold_decision"] == "bid" for j in affected)}
        print(persona, {k: v for k, v in report[persona].items() if k != "suggestions"}, flush=True)
        shutil.rmtree(tmp)
    llm = llm_drafts() if "--llm" in sys.argv else None
    write_result("portfolio_builder_eval.json", {"provenance": provenance({"variant": cls.name, "llm_drafts": bool(llm)}), "summary": report,
                                                 "llm_case_studies": llm})


if __name__ == "__main__":
    main()
