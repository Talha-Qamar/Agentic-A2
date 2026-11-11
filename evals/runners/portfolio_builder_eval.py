"""Extension X3 evaluation: do the builder's suggestions actually unlock bids?

    python -m evals.runners.portfolio_builder_eval

Protocol (per persona, no LLM): run the Fit Matcher logic (deployed retrieval + cross-encoder grading) on the first
half of the dev set -> builder suggestions -> add the top-3 suggested write-ups (outline built only from the repo's
own text, i.e. no new facts) to a copy of the portfolio -> re-run on the HELD-OUT second half -> compare requirement
coverage and fit for jobs that need the suggested skills, and how many jobs cross the bid threshold.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from agent import settings
from agent.nodes.matcher import fit_from
from agent.portfolio_builder import outline_from_repo, suggest
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


def main() -> None:
    cls = variant_class(settings.get("rag.variant"))
    report = {}
    for persona in ("ai_ml_engineer", "fullstack_web_dev", "data_analyst"):
        jobs = [j for j in load_dev(persona) if not j["labels"]["scam"]]
        train, test = jobs[: len(jobs) // 2], jobs[len(jobs) // 2:]
        base_retr = cls(persona)
        sugg = suggest(analyse(base_retr, train), base_retr.corpus.chunks, top=5)
        picks = [s for s in sugg if s["hidden_evidence"]][:3]
        tmp = Path(tempfile.mkdtemp())
        shutil.copytree(ROOT / "data" / "personas" / persona, tmp / persona)
        for s in picks:
            repo = s["hidden_evidence"][0]["repo"]
            (tmp / persona / "case_studies" / f"builder-{repo}-{s['skill'].replace(' ', '_')}.md").write_text(
                f"---\nrepo: {repo}\n---\n" + outline_from_repo(s["skill"], base_retr.corpus.chunks, repo))
        new_corpus = Corpus.from_persona(persona, cls.chunking, None, cls.contextual, base=tmp / persona)
        new_retr = cls(persona, corpus=new_corpus)
        skills = {s["skill"] for s in picks}
        affected = [j for j in test if any(sk in skills for r in extract_requirements(job_text(j)) for sk in extract_skills(r["text"]))]
        before, after = analyse(base_retr, affected), analyse(new_retr, affected)
        report[persona] = {
            "suggestions": [{k: s[k] for k in ("skill", "score", "jobs_affected", "budget_at_stake", "action")} for s in sugg],
            "added_case_studies": [s["skill"] for s in picks], "heldout_jobs_affected": len(affected),
            "coverage_before": round(mean([a["fit"]["coverage"] for a in before]), 4) if before else None,
            "coverage_after": round(mean([a["fit"]["coverage"] for a in after]), 4) if after else None,
            "fit_before": round(mean([a["fit"]["fit_score"] for a in before]), 4) if before else None,
            "fit_after": round(mean([a["fit"]["fit_score"] for a in after]), 4) if after else None,
            "bids_before": sum(a["decision"]["action"] == "bid" for a in before), "bids_after": sum(a["decision"]["action"] == "bid" for a in after),
            "gold_bid_among_affected": sum(j["labels"]["gold_decision"] == "bid" for j in affected)}
        print(persona, {k: v for k, v in report[persona].items() if k != "suggestions"}, flush=True)
        shutil.rmtree(tmp)
    write_result("portfolio_builder_eval.json", {"provenance": provenance({"variant": cls.name}), "summary": report})


if __name__ == "__main__":
    main()
