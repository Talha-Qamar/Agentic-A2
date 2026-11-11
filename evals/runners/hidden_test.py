"""Simulated hidden test: jobs generated at run time from a seed that lives only in a secret (HIDDEN_TEST_SEED),
never in the repo and never used while tuning. Writes the labelled jobs to var/ (git-ignored), loads them into
GigSim's dev pool and runs the decision evaluation against them.

    HIDDEN_TEST_SEED=... python -m evals.runners.hidden_test --per-persona 10
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data" / "generator"))


def main() -> None:
    from jobgen import job_to_dict, make_job
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-persona", type=int, default=10)
    a = ap.parse_args()
    seed = os.environ.get("HIDDEN_TEST_SEED")
    if not seed:
        sys.exit("set HIDDEN_TEST_SEED (kept outside the repo)")
    stats = json.loads((ROOT / "gigsim" / "seed_data" / "market_stats.json").read_text())
    jobs = []
    for persona in ("ai_ml_engineer", "fullstack_web_dev", "data_analyst"):
        rng = random.Random(f"{seed}-{persona}")
        for _ in range(a.per_persona):
            kind = rng.choices(["normal", "scam", "injection"], weights=[0.75, 0.13, 0.12])[0]
            d = job_to_dict(make_job(rng, persona, stats, kind=kind, job_prefix="hid"))
            d["client"]["hidden_preferences"] = {"must_have_skills": d["labels"]["must_have"], "budget_ceiling": d["budget_max"] * 1.1,
                                                 "dislikes_generic_opening": True, "prefers_concise": rng.random() < .5, "reply_propensity": 0.8}
            jobs.append(d)
    var = ROOT / "var"
    var.mkdir(exist_ok=True)
    labelled = var / "hidden_test_jobs.jsonl"
    labelled.write_text("\n".join(json.dumps(j) for j in jobs))
    # make them visible to GigSim (dev pool) for this run only
    sd = ROOT / "gigsim" / "seed_data"
    dev = (sd / "dev_jobs.jsonl").read_text()
    clients = (sd / "clients.jsonl").read_text()
    try:
        with open(sd / "dev_jobs.jsonl", "a") as f:
            for j in jobs:
                f.write("\n" + json.dumps({k: v for k, v in j.items() if k not in ("labels", "requirements")}))
        with open(sd / "clients.jsonl", "a") as f:
            for j in jobs:
                f.write("\n" + json.dumps(j["client"]))
        os.environ["GIGSIM_DB"] = str(var / "hidden_gigsim.db")
        for p in var.glob("hidden_gigsim.db*"):
            p.unlink()
        subprocess.run([sys.executable, "-m", "evals.runners.decision_eval", "--jobs-file", str(labelled), "--out", "hidden_test_results.json"],
                       check=True, cwd=ROOT)
    finally:
        (sd / "dev_jobs.jsonl").write_text(dev)
        (sd / "clients.jsonl").write_text(clients)


if __name__ == "__main__":
    main()
