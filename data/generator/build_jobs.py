"""Generate the labelled dev set and the GigSim live job stream (SYNTHETIC).

    python data/generator/build_jobs.py

Outputs
    evals/datasets/dev_set.jsonl        200 jobs per persona with gold labels (for iteration)
    gigsim/seed_data/stream_jobs.jsonl  jobs GigSim releases over time (labels stripped),
                                        incl. duplicates, scams and planted prompt injections
    gigsim/seed_data/dev_jobs.jsonl     dev jobs as GigSim sees them (labels stripped)
    gigsim/seed_data/clients.jsonl      client histories + hidden preferences

The hidden test set is NOT generated here: evals/runners/hidden_test.py builds it
at run time from a seed held only in a CI secret, so it never enters the repo.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from jobgen import job_to_dict, make_job  # noqa: E402
from persona_bank import PERSONAS  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def hidden_prefs(rng: random.Random, job: dict) -> dict:
    labels = job["labels"]
    return {
        "must_have_skills": labels["must_have"],
        "budget_ceiling": round(job["budget_max"] * rng.uniform(1.0, 1.25), 1),
        "dislikes_generic_opening": rng.random() < 0.7,
        "prefers_concise": rng.random() < 0.5,
        "reply_propensity": round(rng.uniform(0.6, 1.0), 2),
    }


def generate(seed: str, per_persona: int, prefix: str, kinds=(0.78, 0.12, 0.10)) -> list[dict]:
    jobs = []
    for persona in PERSONAS:
        rng = random.Random(f"{seed}-{persona}")
        for _ in range(per_persona):
            kind = rng.choices(["normal", "scam", "injection"], weights=kinds)[0]
            j = make_job(rng, persona, STATS, kind=kind, job_prefix=prefix)
            d = job_to_dict(j)
            d["client"]["hidden_preferences"] = hidden_prefs(rng, d)
            jobs.append(d)
    return jobs


def strip(d: dict) -> dict:
    d = {k: v for k, v in d.items() if k not in ("labels", "requirements")}
    d["client"] = {k: v for k, v in d["client"].items() if k != "hidden_preferences"}
    return d


def main() -> None:
    global STATS
    STATS = json.loads((ROOT / "gigsim" / "seed_data" / "market_stats.json").read_text())
    dev = generate("dev-v1", 200, "dev")
    out = ROOT / "evals" / "datasets"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "dev_set.jsonl", "w") as f:
        for d in dev:
            f.write(json.dumps(d) + "\n")

    # live stream: 60 per persona, then duplicates (re-posts with small edits)
    stream = generate("stream-v1", 60, "live", kinds=(0.72, 0.14, 0.14))
    rng = random.Random("dupes")
    dupes = []
    for d in rng.sample(stream, 18):
        c = json.loads(json.dumps(d))
        c["job_id"] = d["job_id"] + "-r"
        c["title"] = d["title"] + rng.choice([" (reposted)", " - urgent", "!!"])
        c["description"] = d["description"].replace("We are", "We're").replace("Requirements:", "Must haves:")
        c["duplicate_of"] = d["job_id"]
        dupes.append(c)
    stream += dupes
    rng.shuffle(stream)
    for i, d in enumerate(stream):
        d["release_minute"] = i * 7  # GigSim releases one job every ~7 simulated minutes
    sd = ROOT / "gigsim" / "seed_data"
    clients = {}
    with open(sd / "stream_jobs.jsonl", "w") as f:
        for d in stream:
            clients[d["client"]["client_id"]] = d["client"]
            f.write(json.dumps(dict(strip(d), release_minute=d["release_minute"])) + "\n")
    with open(sd / "dev_jobs.jsonl", "w") as f:
        for d in dev:
            clients[d["client"]["client_id"]] = d["client"]
            f.write(json.dumps(strip(d)) + "\n")
    with open(sd / "clients.jsonl", "w") as f:
        for c in clients.values():
            f.write(json.dumps(c) + "\n")
    # stream labels kept for scoring the live-stream exercises (scout dedup, scam, injection)
    with open(out / "stream_labels.jsonl", "w") as f:
        for d in stream:
            f.write(json.dumps({"job_id": d["job_id"], "persona": d["persona"], "labels": d["labels"],
                                "duplicate_of": d.get("duplicate_of")}) + "\n")

    for persona in PERSONAS:
        sub = [d for d in dev if d["persona"] == persona]
        bid = sum(d["labels"]["gold_decision"] == "bid" for d in sub)
        scam = sum(d["labels"]["scam"] for d in sub)
        inj = sum(bool(d["labels"]["injection"]) for d in sub)
        print(f"{persona}: n={len(sub)} bid={bid} skip={len(sub) - bid} scam={scam} injection={inj}")
    print("stream", len(stream), "dupes", len(dupes), "clients", len(clients))


if __name__ == "__main__":
    main()
