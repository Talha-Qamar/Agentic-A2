"""V3 cross-encoder reranking on top of V2 candidates (precision at small k)."""
from __future__ import annotations

from rag.embed import get_reranker
from rag.variants.base import Variant, rrf


class V3Rerank(Variant):
    name = "v3_rerank"
    candidates = 25

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.reranker = get_reranker()

    def hybrid(self, q: str):
        return rrf([self.corpus.dense_search(q, 30), self.corpus.bm25_search(q, 30)])[: self.candidates]

    def search_requirement(self, req, k):
        cands = self.hybrid(req["text"])
        if not cands:
            return []
        docs = [self.corpus._embed_text(self.corpus.by_id[c])[:1500] for c, _ in cands]
        scores = self.reranker.score(req["text"], docs)
        ranked = sorted(zip([c for c, _ in cands], scores), key=lambda x: -x[1])
        return ranked[:k]

    def merge(self, per, k):
        # keep reranker order inside each requirement; RRF across requirements
        return rrf(list(per.values()))[: max(k, 20)]
