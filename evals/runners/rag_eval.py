"""Retrieval evaluation: evidence Recall@5, MRR, nDCG@10 per variant x persona x job type.

    python -m evals.runners.rag_eval --variants all --embedder fastembed
    python -m evals.runners.rag_eval --variants v0_naive,v3_rerank --limit 50

Writes evals/results/rag_benchmark.json and rag_benchmark.csv. Only jobs whose gold label is BID
(and which have gold evidence) are scored for retrieval; V8 refusals are scored on SKIP jobs.
"""
from __future__ import annotations

import argparse
import csv
import time
from collections import defaultdict

from evals.runners.common import (
    RESULTS,
    GoldMapper,
    capped_recall_at,
    job_text,
    load_dev,
    mean,
    mrr,
    ndcg_at,
    pct,
    provenance,
    recall_at,
    write_result,
)
from rag.retriever import VARIANTS, variant_class

NO_LLM = ["v0_naive", "v1_decomposition", "v2_hybrid", "v3_rerank", "v4_outcome_aware", "v5_multivector",
          "v6_contextual", "v8_self_rag", "v9_skill_graph"]


def job_types(job: dict) -> list[str]:
    reqs = job.get("requirements", [])
    t = [f"fit_{job['labels']['fit_level']}", "reqs_4plus" if len(reqs) >= 4 else "reqs_lt4"]
    if any(r["mode"] in ("implied", "vague") for r in reqs):
        t.append("has_implied")
    if job["labels"].get("injection"):
        t.append("injection")
    return t


def run(variants: list[str], embedder: str, limit: int | None, llm_limit: int, out_name: str) -> dict:
    jobs = load_dev(limit_per_persona=limit)
    rows = []
    for v in variants:
        cls = variant_class(v)
        per_persona = {}
        for persona in sorted({j["persona"] for j in jobs}):
            t0 = time.time()
            retr = cls(persona, embedder=embedder)
            per_persona[persona] = (retr, GoldMapper(persona))
            print(f"[{v}] built {persona} corpus in {time.time() - t0:.1f}s ({len(retr.corpus.chunks)} chunks)", flush=True)
        n_llm = defaultdict(int)
        for j in jobs:
            retr, gm = per_persona[j["persona"]]
            if cls.uses_llm and n_llm[j["persona"]] >= llm_limit:
                continue
            gold = j["labels"]["gold_evidence"]
            is_bid = j["labels"]["gold_decision"] == "bid" and gold
            if not is_bid and v != "v8_self_rag":
                continue
            if cls.uses_llm:
                n_llm[j["persona"]] += 1
            res = retr.retrieve(job_text(j), k=10)
            ranked = gm.ranked_projects(res.items)
            row = {"variant": v, "persona": j["persona"], "job_id": j["job_id"], "gold_decision": j["labels"]["gold_decision"],
                   "types": job_types(j), "latency_s": res.latency_s, "n_gold": len(gold), "ranked": ranked[:10],
                   "refused": len(res.unsupported_requirements), "n_reqs": len(res.requirements)}
            if is_bid:
                row.update(recall5=recall_at(ranked, gold, 5), crecall5=capped_recall_at(ranked, gold, 5),
                           mrr=mrr(ranked, gold), ndcg10=ndcg_at(ranked, gold, 10))
            rows.append(row)
        print(f"[{v}] done: {sum(1 for r in rows if r['variant'] == v)} jobs", flush=True)

    def agg(sel):
        bid = [r for r in sel if r["gold_decision"] == "bid"]
        return {"n": len(bid), "recall@5": round(mean([r["recall5"] for r in bid]), 4),
                "capped_recall@5": round(mean([r["crecall5"] for r in bid]), 4), "mrr": round(mean([r["mrr"] for r in bid]), 4),
                "ndcg@10": round(mean([r["ndcg10"] for r in bid]), 4),
                "p50_latency_s": round(pct([r["latency_s"] for r in sel], 50), 4),
                "p95_latency_s": round(pct([r["latency_s"] for r in sel], 95), 4)}

    summary = {}
    for v in variants:
        sv = [r for r in rows if r["variant"] == v]
        entry = {"overall": agg(sv), "by_persona": {p: agg([r for r in sv if r["persona"] == p]) for p in sorted({r["persona"] for r in sv})},
                 "by_type": {}}
        for t in sorted({t for r in sv for t in r["types"]}):
            entry["by_type"][t] = agg([r for r in sv if t in r["types"]])
        if v == "v8_self_rag":
            skip = [r for r in sv if r["gold_decision"] == "skip"]
            bid = [r for r in sv if r["gold_decision"] == "bid"]
            entry["refusal"] = {"skip_jobs_refused_req_frac": round(mean([r["refused"] / max(1, r["n_reqs"]) for r in skip]), 4),
                                "bid_jobs_refused_req_frac": round(mean([r["refused"] / max(1, r["n_reqs"]) for r in bid]), 4)}
        summary[v] = entry
    payload = {"provenance": provenance({"embedder": embedder, "limit_per_persona": limit, "llm_limit": llm_limit}),
               "metric_notes": "recall@5 = |top5 projects ∩ gold| / |gold|; capped_recall@5 divides by min(5,|gold|); "
                               "nDCG@10 uses graded relevance = number of job requirements a project covers.",
               "summary": summary, "rows": rows}
    write_result(out_name, payload)
    with open(RESULTS / out_name.replace(".json", ".csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["variant", "persona", "n", "recall@5", "capped_recall@5", "mrr", "ndcg@10", "p95_latency_s"])
        for v, e in summary.items():
            o = e["overall"]
            w.writerow([v, "all", o["n"], o["recall@5"], o["capped_recall@5"], o["mrr"], o["ndcg@10"], o["p95_latency_s"]])
            for p, o in e["by_persona"].items():
                w.writerow([v, p, o["n"], o["recall@5"], o["capped_recall@5"], o["mrr"], o["ndcg@10"], o["p95_latency_s"]])
    for v, e in summary.items():
        o = e["overall"]
        print(f"{v:18s} n={o['n']:3d} R@5={o['recall@5']:.3f} cR@5={o['capped_recall@5']:.3f} MRR={o['mrr']:.3f} "
              f"nDCG@10={o['ndcg@10']:.3f} p95={o['p95_latency_s']:.3f}s")
    return payload


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="all")
    ap.add_argument("--embedder", default=None)
    ap.add_argument("--limit", type=int, default=None, help="jobs per persona")
    ap.add_argument("--llm-limit", type=int, default=30, help="max jobs per persona for LLM-using variants")
    ap.add_argument("--out", default="rag_benchmark.json")
    a = ap.parse_args()
    vs = NO_LLM + ["v7_hyde"] if a.variants == "all" else (NO_LLM if a.variants == "nollm" else a.variants.split(","))
    assert all(v in VARIANTS for v in vs), vs
    from agent import settings
    run(vs, a.embedder or settings.get("embeddings.backend"), a.limit, a.llm_limit, a.out)
