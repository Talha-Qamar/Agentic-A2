"""V5 multi-vector items: summaries, READMEs and code are searched as separate vector spaces and
aggregated per project, so a repo whose README looks irrelevant can still win on its code."""
from __future__ import annotations

from collections import defaultdict

from rag.variants.base import Variant, rrf

KINDS = {"summary": ("case_study", "review", "cv"), "readme": ("readme",), "code": ("code",), "proposal": ("proposal",)}


class V5MultiVector(Variant):
    name = "v5_multivector"

    def search_requirement(self, req, k):
        q = req["text"]
        qv = self.corpus.qvec([q])[0]
        item_score: dict[str, float] = defaultdict(float)
        best_chunk: dict[str, tuple[str, float]] = {}
        for kind, types in KINDS.items():
            hits = rrf([self.corpus.dense_search(q, 10, types, qv=qv), self.corpus.bm25_search(q, 10, types)])[:8]
            for rank, (cid, s) in enumerate(hits):
                c = self.corpus.by_id[cid]
                item = c.get("project") or c.get("item_id") or cid
                contrib = 1.0 / (60 + rank + 1)
                item_score[item] = max(item_score[item], contrib) + 0.3 * contrib  # max + bonus for multi-view agreement
                if item not in best_chunk or s > best_chunk[item][1]:
                    best_chunk[item] = (cid, s)
        ranked = sorted(item_score.items(), key=lambda x: -x[1])[:k]
        return [(best_chunk[item][0], score) for item, score in ranked]
