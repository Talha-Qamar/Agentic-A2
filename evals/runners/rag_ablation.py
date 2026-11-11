"""Ablate the best retrieval pipeline (V9 skill graph) one component at a time on the dev set.
    python -m evals.runners.rag_ablation"""
from __future__ import annotations

from evals.runners.common import GoldMapper, job_text, load_dev, mean, mrr, ndcg_at, provenance, recall_at, write_result
from rag.variants.v9_skill_graph import V9SkillGraph

CONFIGS = {"full": {}, "-decomposition": {"decomposition": False}, "-outcome_boost": {"outcome_boost": False},
           "-dense_tiebreak": {"dense_tiebreak": False}, "-hybrid_fallback": {"hybrid_fallback": False}, "+rerank": {"rerank": True}}


def main() -> None:
    jobs = [j for j in load_dev() if j["labels"]["gold_decision"] == "bid" and j["labels"]["gold_evidence"]]
    res = {}
    for name, opts in CONFIGS.items():
        rows = []
        for persona in sorted({j["persona"] for j in jobs}):
            v, gm = V9SkillGraph(persona, **opts), GoldMapper(persona)
            for j in [x for x in jobs if x["persona"] == persona]:
                ranked = gm.ranked_projects(v.retrieve(job_text(j), k=10).items)
                g = j["labels"]["gold_evidence"]
                implied = any(r["mode"] in ("implied", "vague") for r in j["requirements"])
                rows.append({"r5": recall_at(ranked, g, 5), "mrr": mrr(ranked, g), "ndcg": ndcg_at(ranked, g, 10), "implied": implied})
        res[name] = {"n": len(rows), "recall@5": round(mean([r["r5"] for r in rows]), 4), "mrr": round(mean([r["mrr"] for r in rows]), 4),
                     "ndcg@10": round(mean([r["ndcg"] for r in rows]), 4),
                     "recall@5_has_implied": round(mean([r["r5"] for r in rows if r["implied"]]), 4),
                     "recall@5_explicit_only": round(mean([r["r5"] for r in rows if not r["implied"]]), 4)}
        print(name, res[name], flush=True)
    write_result("rag_ablation.json", {"provenance": provenance(), "summary": res})


if __name__ == "__main__":
    main()
