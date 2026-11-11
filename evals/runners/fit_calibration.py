"""Set the bid/watch fit thresholds by measurement on the dev set (no LLM; deployed retrieval + Fit Matcher grading).

    python -m evals.runners.fit_calibration

Split per persona: jobs 100..199 tune the thresholds, jobs 0..99 check them (decision_eval samples from 0..99, so the
reported end-to-end numbers never use tuning jobs). Only the fit threshold is calibrated here: scam is taken from the
label and the budget rule is the deterministic floor check, so the sweep isolates the matcher.
"""
from __future__ import annotations

import json

from agent import settings
from agent.nodes.matcher import fit_from
from evals.runners.common import job_text, load_dev, provenance, write_result
from rag.requirements import extract_requirements
from rag.retriever import variant_class

ROOT = settings.ROOT


def budget_ok(job: dict, floor: float) -> bool:
    bmax = float(job.get("budget_max") or 0)
    return bmax >= floor * 0.8 if job.get("budget_type") == "hourly" else bmax >= floor * 4


def f1(rows, t):
    tp = sum(r["gold"] and r["fit"] >= t and r["ok"] for r in rows)
    fp = sum((not r["gold"]) and r["fit"] >= t and r["ok"] for r in rows)
    fn = sum(r["gold"] and not (r["fit"] >= t and r["ok"]) for r in rows)
    p = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    return {"t": t, "precision": round(p, 4), "recall": round(rc, 4), "f1": round(2 * p * rc / (p + rc), 4) if p + rc else 0.0}


def main() -> None:
    cls = variant_class(settings.get("rag.variant"))
    rows = {"tune": [], "check": []}
    for persona in ("ai_ml_engineer", "fullstack_web_dev", "data_analyst"):
        floor = json.loads((ROOT / "data" / "personas" / persona / "profile.json").read_text())["hourly_floor"]
        retr = cls(persona)
        for i, j in enumerate(load_dev(persona)):
            if j["labels"]["scam"]:
                continue
            reqs = extract_requirements(job_text(j))
            res = retr.retrieve(job_text(j), requirements=reqs, k=8)
            fit = fit_from(reqs, res.per_requirement, res.unsupported_requirements)
            rows["tune" if i >= 100 else "check"].append({"job_id": j["job_id"], "persona": persona, "fit": fit.fit_score,
                                                           "coverage": fit.coverage, "gold": j["labels"]["gold_decision"] == "bid",
                                                           "gold_coverage": j["labels"]["coverage"], "ok": budget_ok(j, floor)})
        print(persona, "done", flush=True)
    grid = [round(x * 0.025, 3) for x in range(4, 33)]
    sweep = [f1(rows["tune"], t) for t in grid]
    best = max(sweep, key=lambda r: (r["f1"], -abs(r["t"] - 0.5)))
    watch = round(max(0.0, best["t"] - 0.15), 3)
    check = f1(rows["check"], best["t"])
    default = f1(rows["check"], 0.55)
    gold_bid_fit = sorted(r["fit"] for r in rows["tune"] if r["gold"])
    print("tune best", best, "| check at best", check, "| check at old default 0.55", default)
    write_result("fit_calibration.json", {
        "provenance": provenance({"variant": cls.name, "split": "tune=dev jobs 100-199 per persona, check=0-99"}),
        "summary": {"fit_bid": best["t"], "fit_watch": watch, "tune": best, "check": check, "check_at_previous_default_0.55": default,
                    "n_tune": len(rows["tune"]), "n_check": len(rows["check"]),
                    "gold_bid_fit_median_tune": gold_bid_fit[len(gold_bid_fit) // 2] if gold_bid_fit else None},
        "sweep": sweep, "rows": rows})


if __name__ == "__main__":
    main()
