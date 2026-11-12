"""Why did the cross-encoder make retrieval worse? Compare what V2 (hybrid) and V3 (V2 + cross-encoder) put in the
top 5 per requirement: share of each document type, and whether the chunk belongs to a gold project.

    python -m evals.runners.rerank_analysis --limit 40      # -> evals/results/rerank_analysis.json
"""
from __future__ import annotations

import argparse
from collections import Counter

from evals.runners.common import GoldMapper, job_text, load_dev, provenance, write_result
from rag.retriever import variant_class


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40)
    a = ap.parse_args()
    jobs = [j for j in load_dev(limit_per_persona=a.limit) if j["labels"]["gold_decision"] == "bid" and j["labels"]["gold_evidence"]]
    out = {}
    for v in ("v2_hybrid", "v3_rerank"):
        cls = variant_class(v)
        types, gold_hits, total, proof_types = Counter(), 0, 0, Counter()
        for persona in sorted({j["persona"] for j in jobs}):
            retr, gm = cls(persona), GoldMapper(persona)
            for j in (x for x in jobs if x["persona"] == persona):
                gold = j["labels"]["gold_evidence"]
                res = retr.retrieve(job_text(j), k=10)
                for items in res.per_requirement.values():
                    for e in items[:5]:
                        total += 1
                        types[e["type"]] += 1
                        proj = gm.ranked_projects([e])
                        if proj and proj[0] in gold:
                            gold_hits += 1
                            proof_types[e["type"]] += 1
        out[v] = {"chunks": total, "type_share": {t: round(n / total, 4) for t, n in types.most_common()},
                  "gold_project_share": round(gold_hits / total, 4) if total else None,
                  "gold_hit_types": {t: round(n / max(1, gold_hits), 4) for t, n in proof_types.most_common()}}
        print(v, out[v], flush=True)
    write_result("rerank_analysis.json", {"provenance": provenance({"jobs": len(jobs)}), "summary": out})


if __name__ == "__main__":
    main()
